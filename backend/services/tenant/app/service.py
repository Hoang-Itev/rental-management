"""P04: tenants, DRAFT contracts, versioned [from,to) prices, DRAFT -> SCHEDULED."""
from __future__ import annotations
from datetime import date, datetime, timezone, time, timedelta
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

VN = timezone(timedelta(hours=7))  # Vietnam has no DST

def _boundary(day: date) -> datetime:
    return datetime.combine(day, time.min, tzinfo=VN)

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

    def expiring_contracts(self, within_days=7, page=1, page_size=20, *, today=None):
        today = today or datetime.now(VN).date()
        conditions = (
            m.Contract.status == 'ACTIVE',
            m.Contract.actual_end_date.is_(None),
            m.Contract.end_date.between(today, today + timedelta(days=within_days)),
        )
        return repo.page(self.db, m.Contract, page, page_size, conditions,
                         order=m.Contract.end_date)

    def cancel(self, contract_id: UUID, reason: str, actor_id: UUID | None = None):
        with self.db.begin():
            contract = self._get(m.Contract, contract_id, lock=True)
            if contract.status == 'CANCELLED':
                return contract
            if contract.status not in ('DRAFT', 'SCHEDULED'):
                raise invalid('Only unstarted contracts can be cancelled')
            if contract.actual_end_date is not None:
                raise invalid('Contract already has a recorded handover')
            contract.status = 'CANCELLED'
            repo.add(self.db, m.ContractEvent(
                id=uuid4(), contract_id=contract.id, event_type='CANCELLED',
                occurred_at=datetime.now(timezone.utc), actor_id=actor_id,
                reason=reason, details={'reason': reason},
            ))
            self.db.flush()
        return contract

    def create_contract(self,data:s.ContractCreate,actor_id:UUID|None=None):
        # A DRAFT may be saved for an INACTIVE room, but the room must exist.
        room=self._room(data.room_id,operational=False)
        try:
            with self.db.begin():
                self._get(m.Tenant,data.representative_tenant_id)
                row=repo.add(self.db,m.Contract(
                    id=uuid4(), contract_code=data.contract_code,room_id=data.room_id,
                    room_code_snapshot=room.room_code, representative_tenant_id=data.representative_tenant_id,
                    start_date=data.start_date,end_date=data.end_date,status='DRAFT',deposit_amount=data.deposit_amount))
                item=data.initial_terms
                repo.add(self.db,m.ContractTerm(id=uuid4(),contract_id=row.id,**item.model_dump()))
                self._event(self.db,row.id,'CREATED',actor_id=actor_id)
            return row
        except IntegrityError as exc:
            raise invalid('Duplicate contract code or invalid database constraint') from exc

    def patch_contract(self, contract_id: UUID, data: s.ContractPatch):
        try:
            with self.db.begin():
                row = self._get(m.Contract, contract_id, lock=True)
                if row.status != 'DRAFT':
                    raise invalid('Only DRAFT contracts can be edited')
                changes = data.model_dump(exclude_unset=True)
                start = changes.get('start_date', row.start_date)
                end = changes.get('end_date', row.end_date)
                if end < start or end == date.max:
                    raise invalid('Invalid contract date interval')
                if 'representative_tenant_id' in changes:
                    self._get(m.Tenant, changes['representative_tenant_id'])
                terms = repo.terms(self.db, contract_id)
                if 'start_date' in changes:
                    if not terms:
                        raise invalid('Missing initial term')
                    first = terms[0]
                    if first.effective_to is not None and start >= first.effective_to:
                        raise invalid('New start date invalidates first price term')
                    if len(terms) > 1 and start >= terms[1].effective_from:
                        raise invalid('New start date crosses the next price term')
                    first.effective_from = start
                if 'end_date' in changes:
                    exclusive_end = _end_exclusive(end)
                    for term in terms:
                        if term.effective_from >= exclusive_end:
                            raise invalid('Price term starts after new contract end')
                        if term.effective_to is not None and term.effective_to > exclusive_end:
                            raise invalid('Price term extends beyond new contract end')
                for key, value in changes.items():
                    setattr(row, key, value)
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

    @staticmethod
    def _outbox(db: Session, contract: m.Contract, kind: str, effective_at: datetime):
        """State transition and event persist in the SAME tenant_db transaction."""
        eid = uuid4()
        body = {
            'event_id': str(eid), 'event_type': kind, 'event_version': 1,
            'occurred_at': datetime.now(timezone.utc).isoformat(),
            'effective_at': effective_at.isoformat(),
            'correlation_id': str(uuid4()), 'aggregate_id': str(contract.id),
            'data': {'contract_id': str(contract.id), 'room_id': str(contract.room_id),
                     'start_date': contract.start_date.isoformat(),
                     'end_date': contract.end_date.isoformat()},
        }
        if kind == 'ContractEnded':
            body['data']['actual_end_date'] = contract.actual_end_date.isoformat()
            body['data']['end_reason'] = contract.end_reason
        repo.add(db, m.OutboxEvent(id=eid, aggregate_type='Contract',
            aggregate_id=contract.id, event_type=kind, event_version=1,
            payload=body, dedupe_key=f'contract:{kind}:{contract.id}'))

    def activate(self, contract_id: UUID, *, now: datetime | None = None):
        """Activate a due SCHEDULED contract, never before local midnight.

        Room service is authoritative for current occupancy, Tenant's GiST
        exclusion constraint for the planned booking period.
        """
        now = now or datetime.now(timezone.utc)
        if now.tzinfo is None:
            raise ValueError('now must be timezone-aware')
        try:
            with self.db.begin():
                c = self._get(m.Contract, contract_id, lock=True)
                if c.status == 'ACTIVE':
                    return c
                if c.status != 'SCHEDULED':
                    raise invalid('Only SCHEDULED contracts can activate')
                if now < _boundary(c.start_date):
                    raise invalid('Contract start is in the future')
                if now >= _boundary(_end_exclusive(c.end_date)):
                    raise invalid('Contract scheduled period has already expired')
                if repo.active_occupant(self.db, c.room_id, c.id):
                    raise invalid('Room already has an ACTIVE or EXPIRED_PENDING contract')
                if repo.actual_occupancy_intersects_start(self.db, c.room_id, c.start_date, c.id):
                    raise invalid('Contract start overlaps recorded actual occupancy')
                state = self._room(c.room_id, operational=True)
                if state.occupancy_contract_id not in (None, c.id):
                    raise invalid('Room is physically occupied; retry after ContractEnded')
                c.status = 'ACTIVE'
                self._event(self.db, c.id, 'STARTED', details={'effective_at': _boundary(c.start_date).isoformat()})
                self._outbox(self.db, c, 'ContractStarted', _boundary(c.start_date))
                self.db.flush()
            return c
        except IntegrityError as exc:
            raise invalid('Concurrent contract activation conflict') from exc

    def mark_expired(self, contract_id: UUID, *, now: datetime | None = None):
        now = now or datetime.now(timezone.utc)
        if now.tzinfo is None:
            raise ValueError('now must be timezone-aware')
        with self.db.begin():
            c = self._get(m.Contract, contract_id, lock=True)
            if c.status == 'EXPIRED_PENDING':
                return c
            if c.actual_end_date is not None:
                raise invalid('Contract handover already recorded')
            if c.status != 'ACTIVE' or now < _boundary(_end_exclusive(c.end_date)):
                raise invalid('Contract has not reached expiry')
            c.status = 'EXPIRED_PENDING'
            self.db.flush()
        # EXPIRED_PENDING is still physically OCCUPIED. No ContractEnded.
        return c

    def renew(self, contract_id: UUID, new_end_date: date,
              reason: str | None = None, new_terms: s.TermInput | None = None):
        try:
            with self.db.begin():
                c = self._get(m.Contract, contract_id, lock=True)
                if c.actual_end_date is not None:
                    raise invalid('Cannot renew after handover is recorded')
                if c.status not in ('SCHEDULED', 'ACTIVE', 'EXPIRED_PENDING'):
                    raise invalid('Only confirmed, not-ended contracts can renew')
                old_end = c.end_date
                if new_end_date <= old_end or new_end_date == date.max:
                    raise invalid('New end date must extend contract')
                if repo.overlapping(self.db, c.room_id, _end_exclusive(old_end), new_end_date, c.id):
                    raise invalid('Extension overlaps another confirmed contract')
                terms = repo.terms(self.db, c.id)
                if not terms:
                    raise invalid('Contract has no price terms')
                last = terms[-1]
                next_day = _end_exclusive(old_end)
                if new_terms is not None:
                    if new_terms.effective_from != next_day:
                        raise invalid('Renewal price must start on day after previous end')
                    if (
                        new_terms.effective_to is not None
                        and new_terms.effective_to != _end_exclusive(new_end_date)
                    ):
                        raise invalid('Renewal price must cover the full extended period')
                    if last.effective_to is not None and last.effective_to != next_day:
                        raise invalid('Existing price history does not cover original period')
                    last.effective_to = next_day
                    self.db.flush()
                    repo.add(self.db, m.ContractTerm(id=uuid4(), contract_id=c.id,
                                                     **new_terms.model_dump()))
                elif last.effective_to is not None:
                    if last.effective_to != next_day:
                        raise invalid('Cannot renew through a gap in price history')
                    last.effective_to = None
                c.end_date = new_end_date
                if c.status == 'EXPIRED_PENDING':
                    # Renewing an overdue occupant reactivates it only if still in the new period.
                    now = datetime.now(VN)
                    if now < _boundary(_end_exclusive(new_end_date)):
                        c.status = 'ACTIVE'
                self._event(self.db, c.id, 'EXTENDED', details={
                    'old_end_date': old_end.isoformat(),
                    'new_end_date': new_end_date.isoformat(), 'reason': reason or ''})
                self.db.flush()
            return c
        except IntegrityError as exc:
            raise invalid('Extension violates confirmed contract period exclusion') from exc

    
    def end_contract(self, contract_id: UUID, actual_end_date: date, reason: str,
                     actor_id: UUID | None = None, *, now: datetime | None = None):
        now = now or datetime.now(timezone.utc)
        if now.tzinfo is None:
            raise ValueError('now must be timezone-aware')
        if actual_end_date > now.astimezone(VN).date():
            raise invalid('Cannot end a contract on a future date')
        if not reason.strip():
            raise invalid('Termination reason is required')

        try:
            with self.db.begin():
                c = self._get(m.Contract, contract_id, lock=True)

                if c.status == 'ENDED':
                    if c.actual_end_date == actual_end_date:
                        return c
                    raise invalid('Contract already ended on another date')

                if c.status not in ('ACTIVE', 'EXPIRED_PENDING'):
                    raise invalid('Only occupied contracts can end')

                if actual_end_date < c.start_date:
                    raise invalid('End date before contract start')

                if c.actual_end_date is not None:
                    if c.actual_end_date != actual_end_date:
                        raise invalid('Handover date already recorded')
                else:
                    c.actual_end_date = actual_end_date
                    c.end_reason = reason

                effective = _boundary(_end_exclusive(actual_end_date))

                # Before midnight: record handover, keep occupancy.
                if now >= effective:
                    c.status = 'ENDED'
                    self._event(
                        self.db, c.id, 'ENDED', actor_id=actor_id,
                        details={
                            'effective_at': effective.isoformat(),
                            'reason': c.end_reason
                        }
                    )
                    self._outbox(self.db, c, 'ContractEnded', effective)

                self.db.flush()

            return c

        except IntegrityError as exc:
            raise invalid('Unable to record actual contract end') from exc

