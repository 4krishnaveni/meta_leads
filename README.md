# Meta Lead Ads → React Native (live leads PoC)

When a Meta Lead Ad form is submitted, the lead appears live in an already-open
React Native screen with no action on the device.

## Architecture

Meta Lead Testing Tool → Meta webhook (leadgen) → FastAPI backend (via VS Code Dev Tunnel)
→ Graph API fetch of lead details → WebSocket broadcast → React Native app

The webhook only carries a `leadgen_id`, so the backend fetches the lead's
fields from the Graph API, then pushes the lead to all connected app clients.

## Setup

### Meta
1. Business app with the Webhooks product; Page object subscribed to `leadgen`.
2. A Facebook Page with a published Instant Form.
3. Page access token with `leads_retrieval`, `pages_show_list`,
   `pages_manage_metadata`, `pages_read_engagement`, `pages_manage_ads`.
4. Subscribe the app to the Page: `POST /{PAGE_ID}/subscribed_apps?subscribed_fields=leadgen`

### Backend
```powershell
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env   # then fill in the values
uvicorn main:app --host 0.0.0.0 --port 8000
```

### Public URL (VS Code Dev Tunnels)
Meta can only call a public HTTPS address, so the backend is exposed with VS Code's
built-in port forwarding:

1. In VS Code, open the **Ports** tab and click **Forward a Port**, then enter `8000`.
2. Right-click the port and set **Port Visibility → Public**.
3. Copy the forwarded address (for example `https://<id>-8000.inc1.devtunnels.ms`).
4. In the Meta app dashboard, go to **Webhooks**, choose the **Page** object, and set the
   callback URL to `https://<forwarded-address>/webhook` with your verify token.
   Click **Verify and Save**, then subscribe to the `leadgen` field.

The forwarded address can change if the tunnel is recreated, so update the Meta callback
URL and `BACKEND_HOST` (below) whenever it does. On the first browser visit, Dev Tunnels
shows a one-time warning page. Webhook and WebSocket traffic is not affected by it.

### Mobile
```powershell
cd mobile
npm install
```
Set `BACKEND_HOST` in `App.js` to your forwarded host (no `https://`), then:
```powershell
npx expo start --tunnel
```
Scan the QR code with Expo Go. (`--tunnel` requires a free Expo account login.)

## Test
Open the Lead Ads Testing Tool, choose the Page and form, click "Create lead".
The lead appears in the app within a few seconds.
(`POST /debug/fake-lead` is a local helper for testing without Meta.)

## Assumptions
- Leads are stored in memory and reset on restart (a database would be used in production).
- Development-mode Meta app; the Page and form are mine; leads come from the Testing Tool.
- Backend is exposed through a VS Code Dev Tunnel (public port forwarding).
- The Page access token is generated manually and is short-lived; production would use a long-lived token and refresh.
- WebSocket was chosen because the screen is already open; a closed app would need push (FCM).
- Single-user PoC with no WebSocket auth; webhook requests are verified by signature.
- Duplicate webhook deliveries are ignored by lead ID; the app auto-reconnects.