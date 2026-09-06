# GitHub App OAuth for FRIDAY

FRIDAY supports GitHub App user authorization so the GitHub Agent can act on behalf of the signed-in GitHub user. GitHub recommends GitHub Apps for fine-grained permissions and short-lived user access tokens.

## 1. Create the GitHub App

In GitHub, create a GitHub App under your account settings.

Use these local-development settings:

- Callback URL: `http://127.0.0.1:8000/auth/github/callback`
- Enable user authorization (OAuth).
- Keep user access tokens expiring and enable refresh tokens.
- Request only the repository permissions FRIDAY needs. Start read-only.

Recommended initial permissions:

- Repository metadata: Read-only
- Contents: Read-only
- Pull requests: Read-only
- Issues: Read-only
- Commit statuses: Read-only
- Actions: Read-only

FRIDAY does not need write permissions for repository explanation or inspection.

## 2. Configure `.env`

Copy `.env.example` to `.env` and fill in:

```env
GITHUB_APP_CLIENT_ID=...
GITHUB_APP_CLIENT_SECRET=...
GITHUB_REDIRECT_URI=http://127.0.0.1:8000/auth/github/callback
GITHUB_ENCRYPTION_KEY=...
GITHUB_FRONTEND_URL=http://localhost:3000
```

Generate the encryption key with:

```powershell
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Never commit the client secret, encryption key, or generated connection file.

## 3. Start FRIDAY

```powershell
git pull
uvicorn core.main:app --host 127.0.0.1 --port 8000
```

Start the web app as usual, then open:

`http://localhost:3000/github`

Select **Connect GitHub** and authorize the FRIDAY GitHub App.

## 4. Verify

The backend exposes:

- `GET /auth/github/status`
- `GET /auth/github`
- `GET /auth/github/callback`
- `POST /auth/github/disconnect`

After authorization, FRIDAY stores the GitHub user token encrypted in `.friday/github_connection.enc` and loads it into the existing GitHub Agent. Refresh tokens are used automatically when the access token is close to expiry.

Then test:

```text
explain orbit repo of mine
explain minor_project-TPO repo of mine
explain ai_test repo of mine
```
