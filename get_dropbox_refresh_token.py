#!/usr/bin/env python3
"""Helper script to obtain a Dropbox refresh token using OAuth2 with PKCE.

This script will:
1. Generate a PKCE code verifier and challenge
2. Open your browser to authorize the app
3. Start a local server to receive the callback
4. Exchange the authorization code for a refresh token
5. Display the refresh token to copy into your .env file

Usage:
    python get_dropbox_refresh_token.py
"""
import hashlib
import base64
import secrets
import sys
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlencode, urlparse

import click
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

APP_KEY = os.getenv("DROPBOX_APP_KEY")
REDIRECT_URI = "http://localhost:8080/callback"
PORT = 8080

# Global to store the authorization code
auth_code = None


def generate_pkce_pair():
    """Generate PKCE code verifier and challenge."""
    code_verifier = secrets.token_urlsafe(96)[:128]
    code_challenge = hashlib.sha256(code_verifier.encode()).digest()
    code_challenge = base64.urlsafe_b64encode(code_challenge).rstrip(b"=").decode("ascii")
    return code_verifier, code_challenge


class CallbackHandler(BaseHTTPRequestHandler):
    """Handle the OAuth callback from Dropbox."""
    
    def log_message(self, format, *args):
        """Suppress default logging."""
        pass
    
    def do_GET(self):
        """Handle GET request for OAuth callback."""
        global auth_code
        
        # Parse the query parameters
        query = urlparse(self.path).query
        params = parse_qs(query)
        
        if "code" in params:
            auth_code = params["code"][0]
            
            # Send success response
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            
            html = """
            <html>
            <head><title>Authorization Successful</title></head>
            <body style="font-family: Arial, sans-serif; padding: 50px; text-align: center;">
                <h1 style="color: #0061ff;">✓ Authorization Successful!</h1>
                <p>You can close this window and return to your terminal.</p>
            </body>
            </html>
            """
            self.wfile.write(html.encode())
        else:
            error = params.get("error", ["Unknown error"])[0]
            error_desc = params.get("error_description", [""])[0]
            
            self.send_response(400)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            
            html = f"""
            <html>
            <head><title>Authorization Failed</title></head>
            <body style="font-family: Arial, sans-serif; padding: 50px; text-align: center;">
                <h1 style="color: red;">✗ Authorization Failed</h1>
                <p><strong>Error:</strong> {error}</p>
                <p>{error_desc}</p>
            </body>
            </html>
            """
            self.wfile.write(html.encode())


def get_refresh_token(app_key: str, auth_code: str, code_verifier: str) -> dict:
    """Exchange authorization code for refresh token."""
    import requests
    
    token_url = "https://api.dropboxapi.com/oauth2/token"
    
    data = {
        "code": auth_code,
        "grant_type": "authorization_code",
        "code_verifier": code_verifier,
        "client_id": app_key,
        "redirect_uri": REDIRECT_URI,
    }
    
    response = requests.post(token_url, data=data)
    response.raise_for_status()
    
    return response.json()


@click.command()
def main():
    """Obtain a Dropbox refresh token."""
    if not APP_KEY:
        click.echo(click.style("✗ Error: DROPBOX_APP_KEY not found in .env file", fg="red"))
        sys.exit(1)
    
    click.echo(click.style("🔐 Dropbox Refresh Token Generator", fg="cyan", bold=True))
    click.echo()
    click.echo(f"App Key: {APP_KEY}")
    click.echo(f"Redirect URI: {REDIRECT_URI}")
    click.echo()
    
    # Generate PKCE pair
    code_verifier, code_challenge = generate_pkce_pair()
    
    # Build authorization URL
    auth_params = {
        "client_id": APP_KEY,
        "response_type": "code",
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "redirect_uri": REDIRECT_URI,
        "token_access_type": "offline",  # Request refresh token
    }
    
    auth_url = f"https://www.dropbox.com/oauth2/authorize?{urlencode(auth_params)}"
    
    click.echo(click.style("Step 1: Authorize the application", fg="yellow", bold=True))
    click.echo(f"Opening browser to: {auth_url}")
    click.echo()
    
    # Open browser
    webbrowser.open(auth_url)
    
    click.echo(click.style("Step 2: Starting local callback server...", fg="yellow", bold=True))
    click.echo(f"Listening on http://localhost:{PORT}")
    click.echo()
    click.echo("Please complete the authorization in your browser...")
    click.echo()
    
    # Start local server to receive callback
    server = HTTPServer(("localhost", PORT), CallbackHandler)
    
    # Handle one request (the callback)
    server.handle_request()
    server.server_close()
    
    if not auth_code:
        click.echo(click.style("✗ Failed to receive authorization code", fg="red"))
        sys.exit(1)
    
    click.echo(click.style("✓ Received authorization code", fg="green"))
    click.echo()
    
    # Exchange code for tokens
    click.echo(click.style("Step 3: Exchanging code for refresh token...", fg="yellow", bold=True))
    
    try:
        tokens = get_refresh_token(APP_KEY, auth_code, code_verifier)
        
        access_token = tokens.get("access_token")
        refresh_token = tokens.get("refresh_token")
        expires_in = tokens.get("expires_in")
        
        click.echo(click.style("✓ Successfully obtained tokens!", fg="green", bold=True))
        click.echo()
        click.echo(click.style("=" * 80, fg="cyan"))
        click.echo(click.style("Add this to your .env file:", fg="cyan", bold=True))
        click.echo(click.style("=" * 80, fg="cyan"))
        click.echo()
        click.echo(f"DROPBOX_REFRESH_TOKEN={refresh_token}")
        click.echo()
        click.echo(click.style("=" * 80, fg="cyan"))
        click.echo()
        click.echo(click.style("🔄 Token Information:", fg="yellow"))
        click.echo(f"  • Access Token Expires: {expires_in} seconds ({expires_in // 3600} hours)")
        click.echo(f"  • Refresh Token: Never expires (can be used to get new access tokens)")
        click.echo()
        click.echo(click.style("💡 Note:", fg="yellow"))
        click.echo("  The refresh token will automatically renew your access token when it expires.")
        click.echo("  You can also update DROPBOX_ACCESS_TOKEN with the new value shown above if needed.")
        click.echo()
        
    except Exception as e:
        click.echo(click.style(f"✗ Failed to exchange code for tokens: {e}", fg="red"))
        sys.exit(1)


if __name__ == "__main__":
    main()
