"""P04: tenants, DRAFT contracts, versioned [from,to) prices, DRAFT -> SCHEDULED."""
from __future__ import annotations
from datetime import date, datetime, timezone
from uuid import UUID, uuid4
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app import models as m, repository as repo, schemas as s
from app.clients import RoomClient, RoomUnavailable

class TenantError(Exception):
    def __init__(self, status: int, code: str, message: str):
        self.status, self.code, self.message = status, code, message
        super().__init__(message)

def invalid(message): return TenantError(409,'CONFLICT',message)
def missing(what): return TenantError(404,'NOT_FOUND',f'{what} not found')

def _end_exclusive(end: date) -> date:
    if end == date.max:
        raise invalid('End date is out of supported range')
    return date.fromordinal(end.toordinal()+1)

class TenantService:
    def __init__(self, db: Session, room: RoomClient):
        self.db, self.room = db, room

    def _get(self, model, object_id: UUID, *, lock=False):
        row=repo.get(self.db,model,object_id,lock=lock)
        if row is None:
            raise missing(model.__name__)
        return row

    def _room(self, room_id: UUID, *, operational: bool) -> s.RoomValidation:
        try:
            result=self.room.validate(room_id)
        except RoomUnavailable as exc:
            raise TenantError(503,'DEPENDENCY_UNAVAILABLE','Room Service validation unavailable') from exc
        if not result.exists:
            raise missing('Room')
        if operational and not result.operational:
            raise invalid('Room, floor, building or property is INACTIVE')
        return result

    @staticmethod
    def _event(db, contract_id: UUID, kind: str, *, details=None, actor_id=None):
        repo.add(db,m.ContractEvent(id=uuid4(),contract_id=contract_id,event_type=kind,
                                    occurred_at=datetime.now(timezone.utc),actor_id=actor_id,details=details or {}))

    def tenants(self, page=1, page_size=20):
        return repo.page(self.db,m.Tenant,page,page_size,order=m.Tenant.full_name)
    def tenant(self, tenant_id: UUID): return self._get(m.Tenant,tenant_id)

    def create_tenant(self, data: s.TenantCreate):
        try:
            with self.db.begin():
                row=repo.add(self.db,m.Tenant(id=uuid4(),**data.model_dump()))
            return row
        except IntegrityError as exc:
            raise invalid('Tenant database constraint violation') from exc

    def patch_tenant(self, tenant_id: UUID, data: s.TenantPatch):
        try:
            with self.db.begin():
                row=self._get(m.Tenant,tenant_id,lock=True)
                for k,v in data.model_dump(exclude_unset=True).items(): setattr(row,k,v)
                self.db.flush()
            return row
        except IntegrityError as exc:
            raise invalid('Tenant database constraint violation') from exc

    def contracts(self, page=1, page_size=20, room_id=None, status=None):
        c=[]
        if room_id is not None: c.append(m.Contract.room_id==room_id)
        if status is not None: c.append(m.Contract.status==status)
        return repo.page(self.db,m.Contract,page,page_size,c,order=m.Contract.created_at)
    def contract(self, contract_id): return self._get(m.Contract,contract_id)

    def create_contract(self,data:s.ContractCreate,actor_id:UUID|None=None):
        # A DRAFT may be saved for an INACTIVE room, but the room must exist.
        room=self._room(data.room_id,operational=False)
        try:
            with self.db.begin():
                self._get(m.Tenant,data.representative_tenant_id)
                row=repo.add(self.db,m.Contract(
                    id=uuid4(), contract_code=data.contract_code,room_id=data.room_id,
                    room_code_snapshot=room.room_code, representative_tenant_id=data.representative_tenant_id,
                    start_date=data.start_date,end_date=data.end_date,status='DRAFT'))
                item=data.initial_terms
                repo.add(self.db,m.ContractTerm(id=uuid4(),contract_id=row.id,**item.model_dump()))
                self._event(self.db,row.id,'CREATED',actor_id=actor_id)
            return row
        except IntegrityError as exc:
            raise invalid('Duplicate contract code or invalid database constraint') from exc

    def patch_contract(self,contract_id:UUID,data:s.ContractPatch):
        try:
            with self.db.begin():
                row=self._get(m.Contract,contract_id,lock=True)
                if row.status!='DRAFT': raise invalid('Only DRAFT contracts can be edited')
                changes=data.model_dump(exclude_unset=True)
                start=changes.get('start_date',row.start_date)
                end=changes.get('end_date',row.end_date)
                if end<start or end==date.max: raise invalid('Invalid contract date interval')
                if 'representative_tenant_id' in changes:
                    self._get(m.Tenant,changes['representative_tenant_id'])
                for k,v in changes.items(): setattr(row,k,v)
                self.db.flush()
            return row
        except IntegrityError as exc:
            raise invalid('Duplicate contract code or invalid database constraint') from exc

    def terms(self,contract_id):
        self._get(m.Contract,contract_id)
        return repo.terms(self.db,contract_id)

    def add_term(self,contract_id:UUID,data:s.TermInput):
        try:
            with self.db.begin():
                contract=self._get(m.Contract,contract_id,lock=True)
                if contract.status!='DRAFT': raise invalid('Price terms can only be changed while DRAFT')
                if not (contract.start_date < data.effective_from <= contract.end_date):
                    raise invalid('New term must start after the first term and inside contract period')
                if data.effective_to is not None and data.effective_to > _end_exclusive(contract.end_date):
                    raise invalid('Term extends beyond contract end')
                terms=repo.terms(self.db,contract_id)
                if not terms: raise invalid('Missing initial term')
                previous=terms[-1]
                if data.effective_from<=previous.effective_from:
                    raise invalid('Term versions must increase in time')
                if previous.effective_to is not None and previous.effective_to!=data.effective_from:
                    raise invalid('Term versions must be contiguous')
                previous.effective_to=data.effective_from
                self.db.flush()
                row=repo.add(self.db,m.ContractTerm(id=uuid4(),contract_id=contract_id,**data.model_dump()))
            return row
        except IntegrityError as exc:
            raise invalid('Overlapping/invalid contract term versions') from exc

    def events(self,contract_id):
        self._get(m.Contract,contract_id)
        return repo.events(self.db,contract_id)

    def confirm(self,contract_id:UUID,actor_id:UUID|None=None):
        try:
            with self.db.begin():
                contract=self._get(m.Contract,contract_id,lock=True)
                if contract.status=='SCHEDULED': return contract  # safe retry
                if contract.status!='DRAFT': raise invalid('Only DRAFT contracts can be confirmed')
                tenant=self._get(m.Tenant,contract.representative_tenant_id)
                if not tenant.email:
                    raise invalid('Representative payer must have an email address')
                terms=repo.terms(self.db,contract_id)
                if not terms or terms[0].effective_from!=contract.start_date:
                    raise invalid('Price terms do not begin at contract start')
                expected=contract.start_date
                for term in terms:
                    if term.effective_from!=expected: raise invalid('Price term versions contain a gap')
                    expected=term.effective_to or _end_exclusive(contract.end_date)
                if expected < _end_exclusive(contract.end_date):
                    raise invalid('Price terms do not cover entire contract')
                if terms[-1].effective_to is not None and terms[-1].effective_to > _end_exclusive(contract.end_date):
                    raise invalid('Last term extends beyond contract end')
                if repo.overlapping(self.db,contract.room_id,contract.start_date,contract.end_date,contract.id):
                    raise invalid('Room has a confirmed overlapping contract')
                room=self._room(contract.room_id,operational=True)
                contract.room_code_snapshot=room.room_code
                contract.status='SCHEDULED'
                self._event(self.db,contract_id,'CONFIRMED',actor_id=actor_id,
                            details={'start_date':contract.start_date.isoformat(),
                                     'end_date':contract.end_date.isoformat()})
                self.db.flush()  # GiST EXCLUDE is authoritative for concurrent confirms
            return contract
        except IntegrityError as exc:
            raise invalid('Overlapping confirmed contract or database constraint violation') from exc
