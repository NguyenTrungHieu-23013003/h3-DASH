FROM caddy:2.8-alpine

# Install iproute2 for traffic control (tc) and python3 for API
RUN apk update && apk add --no-cache iproute2 python3 iptables

WORKDIR /srv

COPY Caddyfile /etc/caddy/Caddyfile
COPY html /srv/html
COPY video /srv/video
COPY network_api.py /srv/network_api.py

# Create log directory
RUN mkdir -p /var/log/caddy

EXPOSE 443/tcp
EXPOSE 443/udp

# Entrypoint to run Caddy and the Network API
CMD ["sh", "-c", "python3 /srv/network_api.py > /srv/html/network_api_console.log 2>&1 & caddy run --config /etc/caddy/Caddyfile --adapter caddyfile"]