FROM nginx:1.29.1-alpine

# File dell'interfaccia (niente sorgenti Python né test).
COPY frontend/index.html frontend/app.js frontend/api.js frontend/logica.js frontend/stile.css frontend/openapi.json /usr/share/nginx/html/

# L'immagine ufficiale sostituisce le variabili d'ambiente nei template all'avvio
# (BACKEND_INTERNO_URL: indirizzo del back-end nella rete di Compose).
COPY frontend/nginx.conf.template /etc/nginx/templates/default.conf.template

EXPOSE 80
