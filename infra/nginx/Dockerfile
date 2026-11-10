FROM nginx:stable-alpine
# Official nginx entrypoint renders .template with environment variables at startup.
COPY infra/nginx/default.conf /etc/nginx/templates/default.conf.template
COPY infra/nginx/index.html /usr/share/nginx/html/index.html
EXPOSE 80
