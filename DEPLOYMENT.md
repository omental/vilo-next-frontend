# VILO Deployment Runbook (muba.me)

This runbook is for live demo deployment only.

Targets:
- Frontend: `muba.me`
- Backend API: `api.muba.me`

## 1) Server prerequisites
- Ubuntu 22.04+ (or equivalent)
- Python 3.12+
- Node.js 20+
- PostgreSQL 15+
- Nginx
- systemd

## 2) Environment variables
Use these example files as checklists:
- Frontend: `.env.production.example`
- Backend: `backend/.env.production.example`

Do **not** commit real secrets.

## 3) Backend install and run
```bash
cd /opt/vilo/vuexy-next/backend
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

Run migrations:
```bash
cd /opt/vilo/vuexy-next/backend
source .venv/bin/activate
alembic upgrade head
```

Seed demo data (manual only, never auto-run):
```bash
cd /opt/vilo/vuexy-next/backend
source .venv/bin/activate
python scripts/seed_demo_data.py --reset-demo-data
```

Manual API start command:
```bash
cd /opt/vilo/vuexy-next/backend
source .venv/bin/activate
uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 2
```

## 4) Frontend install and run
```bash
cd /opt/vilo/vuexy-next
npm ci
npm run build
npm run start -- --hostname 127.0.0.1 --port 3000
```

## 5) systemd units
### Backend service `/etc/systemd/system/vilo-api.service`
```ini
[Unit]
Description=VILO FastAPI API
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/opt/vilo/vuexy-next/backend
EnvironmentFile=/opt/vilo/vuexy-next/backend/.env
ExecStart=/opt/vilo/vuexy-next/backend/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 2
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

### Frontend service `/etc/systemd/system/vilo-web.service`
```ini
[Unit]
Description=VILO Next.js Web
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/opt/vilo/vuexy-next
EnvironmentFile=/opt/vilo/vuexy-next/.env.production
ExecStart=/usr/bin/npm run start -- --hostname 127.0.0.1 --port 3000
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

Enable/start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable vilo-api vilo-web
sudo systemctl restart vilo-api vilo-web
sudo systemctl status vilo-api vilo-web
```

## 6) Nginx reverse proxy
`/etc/nginx/sites-available/vilo.conf`
```nginx
server {
    listen 80;
    server_name muba.me www.muba.me;

    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}

server {
    listen 80;
    server_name api.muba.me;

    client_max_body_size 60M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Enable site:
```bash
sudo ln -s /etc/nginx/sites-available/vilo.conf /etc/nginx/sites-enabled/vilo.conf
sudo nginx -t
sudo systemctl reload nginx
```

## 7) HTTPS (recommended)
Use Certbot after DNS is pointed:
```bash
sudo certbot --nginx -d muba.me -d www.muba.me -d api.muba.me
```

## 8) Post-deploy checks
- Frontend: `https://muba.me`
- API docs: `https://api.muba.me/docs`
- Login for seeded demo users
- PDF download endpoint works
- Calendar and clients pages load

## 9) Safety notes
- `seed_demo_data.py` is CLI-only and is not called from app startup.
- Never store real secrets in repo.
- Keep `backend/storage/` out of git.
