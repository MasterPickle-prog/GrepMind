import json
import os
import sys
import pickle
import secrets
import smtplib
import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import requests
from functools import wraps

from authlib.integrations.flask_client import OAuth
from dotenv import load_dotenv
from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError

ph = PasswordHasher(
    time_cost=3,
    memory_cost=65536,
    parallelism=4,
    hash_len=32,
    salt_len=16,
    encoding="utf-8",
    type=__import__("argon2").Type.ID
)

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev-secret-key-change-me")

RECAPTCHA_SITE_KEY   = os.getenv("RECAPTCHA_SITE_KEY", "")
RECAPTCHA_SECRET_KEY = os.getenv("RECAPTCHA_SECRET_KEY", "")

RECAPTCHA_THRESHOLD  = 0.5

# ---- Security / admin --------------------------------------------------------
import datetime

ADMIN_EMAIL       = "grepmindscientific@gmail.com"
SECURITY_LOG_FILE = os.path.join(os.path.dirname(__file__), "security_log.json")
BLOCKED_IPS_FILE  = os.path.join(os.path.dirname(__file__), "blocked_ips.json")


def get_client_ip():
    forwarded = request.headers.get("X-Forwarded-For")
    return forwarded.split(",")[0].strip() if forwarded else request.remote_addr


def load_security_log():
    if not os.path.exists(SECURITY_LOG_FILE):
        return []
    with open(SECURITY_LOG_FILE) as f:
        content = f.read().strip()
    try:
        return json.loads(content) if content else []
    except json.JSONDecodeError:
        return []


def save_security_log(log):
    with open(SECURITY_LOG_FILE, "w") as f:
        json.dump(log[-1000:], f, indent=2)   # cap at 1000 entries


def get_ip_geo(ip: str) -> dict:
    """Look up city/country/coords for an IP using ip-api.com (free, no key needed)."""
    if ip in ("127.0.0.1", "::1", "localhost"):
        return {"city": "localhost", "country": "Local", "lat": None, "lon": None}
    try:
        r = requests.get(
            f"http://ip-api.com/json/{ip}?fields=city,regionName,country,lat,lon,status",
            timeout=3
        ).json()
        if r.get("status") == "success":
            city = r.get("city") or r.get("regionName", "")
            return {
                "city":    city,
                "country": r.get("country", ""),
                "lat":     r.get("lat"),
                "lon":     r.get("lon"),
            }
    except Exception:
        pass
    return {}


def log_event(event_type: str, ip: str, details: str = ""):
    log = load_security_log()
    geo = get_ip_geo(ip)
    log.append({
        "type":      event_type,
        "ip":        ip,
        "timestamp": datetime.datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "details":   details,
        "geo":       geo,
    })
    save_security_log(log)


def load_blocked_ips() -> dict:
    if not os.path.exists(BLOCKED_IPS_FILE):
        return {}
    with open(BLOCKED_IPS_FILE) as f:
        content = f.read().strip()
    try:
        return json.loads(content) if content else {}
    except json.JSONDecodeError:
        return {}


def save_blocked_ips(blocked: dict):
    with open(BLOCKED_IPS_FILE, "w") as f:
        json.dump(blocked, f, indent=2)


@app.before_request
def block_banned_ips():
    ip = get_client_ip()
    blocked = load_blocked_ips()
    if ip in blocked:
        log_event("blocked_request", ip, request.path)
        return "Your IP has been blocked.", 403

    # Invalidate sessions when session_version was bumped by admin (expire account)
    if "user_email" in session:
        users = load_users()
        user = users.get(session["user_email"], {})
        stored_ver = user.get("session_version", 0)
        if session.get("session_version", 0) != stored_ver:
            session.clear()
            flash("Your session has been ended by an administrator.")
            return redirect(url_for("signin"))


# ---- Email verification ----

def send_email(to_email: str, subject: str, html_body: str) -> bool:
    """Send an email via SMTP. Configure via .env (see below)."""
    host     = os.getenv("SMTP_HOST",     "smtp.gmail.com")
    port     = int(os.getenv("SMTP_PORT", "587"))
    user     = os.getenv("SMTP_USER",     "")
    password = os.getenv("SMTP_PASSWORD", "")
    sender   = os.getenv("SMTP_FROM",     user)

    if not user or not password:
        print("[Email] SMTP_USER / SMTP_PASSWORD not set — email skipped.")
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = sender
    msg["To"]      = to_email
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP(host, port) as srv:
            srv.ehlo()
            srv.starttls()
            srv.login(user, password)
            srv.sendmail(sender, to_email, msg.as_string())
        print(f"[Email] Sent '{subject}' → {to_email}")
        return True
    except Exception as e:
        print(f"[Email] Failed: {e}")
        return False


def send_verification_email(email: str, token: str) -> bool:
    app_url    = os.getenv("APP_URL", "http://localhost:8080")
    verify_url = f"{app_url}/verify/{token}"
    html = f"""
    <div style="font-family:'Google Sans',sans-serif;max-width:480px;margin:auto;
                background:#000;color:#fff;padding:32px;border-radius:16px">
        <h2 style="margin:0 0 10px">Verify your GrepMind account</h2>
        <p style="color:#aaa;margin-bottom:24px">
            Thanks for signing up. Click the button below to verify your email address.
        </p>
        <a href="{verify_url}"
           style="display:inline-block;padding:12px 26px;background:#fff;
                  color:#000;border-radius:10px;text-decoration:none;font-weight:600">
            Verify Email
        </a>
        <p style="color:#555;font-size:0.82rem;margin-top:28px">
            This link expires in 24 hours. If you didn't create an account, ignore this email.
        </p>
    </div>"""
    return send_email(email, "Verify your GrepMind account", html)


# ---- GrepS model loading ----
# Put your models/ folder next to app.py, or override with GREPS_DIR in .env
GREPS_DIR       = os.getenv("GREPS_DIR", os.path.join(os.path.dirname(__file__), "models"))
CHECKPOINT_PATH  = os.getenv("GREPS_CHECKPOINT", os.path.join(GREPS_DIR, "checkpoints", "final.pt"))
TOKENIZER_PATH   = os.getenv("GREPS_TOKENIZER",  os.path.join(GREPS_DIR, "checkpoints", "tokenizer.pkl"))

greps_model     = None
greps_tokenizer = None
greps_device    = "cpu"

def load_greps():
    """
    Tries to load the trained Vortex model and tokenizer at startup.
    If the checkpoint doesn't exist yet, falls back to the placeholder response.
    """
    global greps_model, greps_tokenizer, greps_device

    if not os.path.exists(CHECKPOINT_PATH):
        print(f"[GrepS] No checkpoint found at {CHECKPOINT_PATH} — using placeholder responses.")
        return
    if not os.path.exists(TOKENIZER_PATH):
        print(f"[GrepS] No tokenizer found at {TOKENIZER_PATH} — using placeholder responses.")
        return

    try:
        sys.path.insert(0, GREPS_DIR)
        from model import GrepMindVortex  # type: ignore

        import torch
        greps_device = (
            "mps"  if torch.backends.mps.is_available()  else
            "cuda" if torch.cuda.is_available()           else
            "cpu"
        )
        print(f"[GrepS] Loading model on {greps_device}…")
        greps_model, _ = GrepMindVortex.load_checkpoint(CHECKPOINT_PATH, device=greps_device)
        greps_model.eval()

        with open(TOKENIZER_PATH, "rb") as f:
            greps_tokenizer = pickle.load(f)

        print("[GrepS] Model ready.")
    except Exception as e:
        print(f"[GrepS] Failed to load model: {e} — using placeholder responses.")
        greps_model     = None
        greps_tokenizer = None


def greps_generate(prompt: str, max_new_tokens: int = 512) -> str:
    """Generate a response from GrepS, or return a placeholder if not loaded."""
    if greps_model is None or greps_tokenizer is None:
        return f"[GrepS not loaded yet] Received: {prompt!r}"

    import torch
    # Wrap in a conversational format so GrepS handles both coding and
    # general questions naturally
    formatted = (
        f"<|code|>\n"
        f"User: {prompt.strip()}\n"
        f"GrepS:"
    )
    bos  = [greps_model.config.bos_token_id]
    ids  = greps_tokenizer.encode(formatted)
    inp  = torch.tensor([bos + ids], dtype=torch.long, device=greps_device)

    out  = greps_model.generate(
        inp,
        max_new_tokens=max_new_tokens,
        temperature=0.8,
        top_k=50,
        top_p=0.95,
        repetition_penalty=1.1,
    )
    raw = greps_tokenizer.decode(out[0].tolist())
    # Strip the prompt prefix from the output so only the reply is returned
    if "GrepS:" in raw:
        raw = raw.split("GrepS:", 1)[-1]
    return raw.strip()


def greps_title(first_message: str) -> str:
    """Ask the model to produce a short 4-6 word title for a conversation."""
    prompt = (
        f"# Summarise the following coding question as a short title (4-6 words, no punctuation):\n"
        f"# Question: {first_message.strip()}\n"
        f"# Title:"
    )
    raw = greps_generate(prompt, max_new_tokens=24)
    # Take only the first line of whatever the model generated
    title = raw.strip().splitlines()[0].strip().lstrip("#").strip()
    # Fallback: truncate the original message if the model returns garbage
    if not title or len(title) > 80:
        title = first_message[:48] + ("…" if len(first_message) > 48 else "")
    return title

def verify_recaptcha(token, action):
    """Returns True if the token passes reCAPTCHA v3 verification.

    Skipped entirely when:
      - RECAPTCHA_SECRET_KEY is not set, OR
      - RECAPTCHA_SKIP=true is set in .env (useful during local dev)
    """
    if os.getenv("RECAPTCHA_SKIP", "").lower() in ("1", "true", "yes"):
        return True  # dev bypass

    if not RECAPTCHA_SECRET_KEY:
        return True  # not configured

    if not token:
        print("[reCAPTCHA] No token received")
        return False

    try:
        resp = requests.post(
            "https://www.google.com/recaptcha/api/siteverify",
            data={
                "secret":   RECAPTCHA_SECRET_KEY,
                "response": token,
            },
            timeout=5,
        ).json()

        print(f"[reCAPTCHA] response: {resp}")

        if not resp.get("success"):
            print(f"[reCAPTCHA] failed: {resp.get('error-codes', [])}")
            return False
        if resp.get("action") != action:
            print(f"[reCAPTCHA] action mismatch: got {resp.get('action')!r}, expected {action!r}")
            return False
        score = resp.get("score", 0)
        if score < RECAPTCHA_THRESHOLD:
            print(f"[reCAPTCHA] score too low: {score} < {RECAPTCHA_THRESHOLD}")
            return False
        return True

    except Exception as e:
        print(f"[reCAPTCHA] exception: {e}")
        return False

oauth = OAuth(app)
google = oauth.register(
    name="google",
    client_id=os.getenv("CLIENT_ID"),
    client_secret=os.getenv("CLIENT_SECRET"),
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)

USERS_FILE = os.path.join(os.path.dirname(__file__), "users.json")


def load_users():
    if not os.path.exists(USERS_FILE):
        save_users({})
        return {}
    with open(USERS_FILE, "r") as f:
        content = f.read().strip()
        if not content:
            save_users({})
            return {}
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            save_users({})
            return {}


def save_users(users):
    with open(USERS_FILE, "w") as f:
        json.dump(users, f, indent=2)


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_email" not in session:
            return redirect(url_for("signin"))
        return view(*args, **kwargs)
    return wrapped


# ---- Email / password auth ----

@app.route("/signin", methods=["GET", "POST"])
def signin():
    if request.method == "POST":
        email    = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        token    = request.form.get("recaptcha_token", "")

        if not verify_recaptcha(token, "signin"):
            flash("reCAPTCHA verification failed. Please try again.")
            return redirect(url_for("signin"))

        users = load_users()
        user  = users.get(email)

        try:
            valid = ph.verify(user.get("password", ""), password)
        except (VerifyMismatchError, VerificationError, InvalidHashError):
            valid = False

        if user and valid:
            # Existing accounts (created before email verification) default to verified
            if not user.get("verified", True):
                flash("Please verify your email before signing in. Check your inbox.")
                log_event("unverified_login", get_client_ip(), f"email: {email}")
                return redirect(url_for("signin"))
            session["user_email"]      = email
            session["session_version"] = user.get("session_version", 0)
            log_event("login", get_client_ip(), f"email: {email}")
            if email == ADMIN_EMAIL:
                return redirect(url_for("security"))
            return redirect(url_for("home"))

        log_event("failed_login", get_client_ip(), f"email: {email}")
        flash("Incorrect email or password.")
        return redirect(url_for("signin"))

    return render_template("signin.html", recaptcha_site_key=RECAPTCHA_SITE_KEY)


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        first_name       = request.form.get("first_name", "").strip()
        last_name        = request.form.get("last_name", "").strip()
        email            = request.form.get("email", "").strip().lower()
        password         = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")
        token            = request.form.get("recaptcha_token", "")

        if not verify_recaptcha(token, "signup"):
            flash("reCAPTCHA verification failed. Please try again.")
            return redirect(url_for("signup"))

        if not first_name or not last_name or not email or not password:
            flash("Please fill out every field.")
            return redirect(url_for("signup"))

        if password != confirm_password:
            flash("Passwords don't match.")
            return redirect(url_for("signup"))

        users = load_users()
        if email in users:
            flash("An account with that email already exists.")
            return redirect(url_for("signup"))

        verify_token   = secrets.token_urlsafe(32)
        verify_expires = (
            datetime.datetime.utcnow() + datetime.timedelta(hours=24)
        ).isoformat(timespec="seconds") + "Z"

        users[email] = {
            "first_name":      first_name,
            "last_name":       last_name,
            "password":        ph.hash(password),
            "verified":        False,
            "verify_token":    verify_token,
            "verify_expires":  verify_expires,
            "session_version": 0,
        }
        save_users(users)

        sent = send_verification_email(email, verify_token)
        if sent:
            flash("Account created! Please check your inbox to verify your email before signing in.")
        else:
            # SMTP not configured — auto-verify so dev/testing still works
            users[email]["verified"] = True
            users[email].pop("verify_token", None)
            users[email].pop("verify_expires", None)
            save_users(users)
            flash("Account created! (Email verification is not configured — you can sign in now.)")

        return redirect(url_for("signin"))

    return render_template("signup.html", recaptcha_site_key=RECAPTCHA_SITE_KEY)


@app.route("/verify/<token>")
def verify_email(token):
    users = load_users()
    now   = datetime.datetime.utcnow().isoformat(timespec="seconds") + "Z"

    for email, user in users.items():
        if user.get("verify_token") == token:
            if user.get("verify_expires", "9999") < now:
                flash("Verification link has expired. Please sign up again or request a new link.")
                return redirect(url_for("signup"))
            users[email]["verified"] = True
            users[email].pop("verify_token",   None)
            users[email].pop("verify_expires", None)
            save_users(users)
            session["user_email"]      = email
            session["session_version"] = users[email].get("session_version", 0)
            flash("Email verified! Welcome to GrepMind.")
            return redirect(url_for("home"))

    flash("Invalid or already-used verification link.")
    return redirect(url_for("signin"))


@app.route("/logout")
def logout():
    session.pop("user_email", None)
    return redirect(url_for("signin"))


# ---- Google OAuth ----

@app.route("/auth/google")
def auth_google():
    redirect_uri = url_for("auth_google_callback", _external=True)
    return google.authorize_redirect(redirect_uri)


@app.route("/auth/google/callback")
def auth_google_callback():
    token = google.authorize_access_token()
    user_info = token.get("userinfo")

    if not user_info:
        flash("Google sign-in failed. Please try again.")
        return redirect(url_for("signin"))

    email = user_info["email"].lower()
    users = load_users()

    if email not in users:
        # Auto-create an account from their Google profile
        users[email] = {
            "first_name": user_info.get("given_name", ""),
            "last_name": user_info.get("family_name", ""),
            "google_id": user_info.get("sub"),
            "password": None,  # Google users have no local password
        }
        save_users(users)

    session["user_email"] = email
    log_event("login", get_client_ip(), f"email: {email} (Google OAuth)")
    if email == ADMIN_EMAIL:
        return redirect(url_for("security"))
    return redirect(url_for("home"))


# ---- Main app ----

@app.route("/")
@login_required
def home():
    users = load_users()
    user = users.get(session["user_email"], {})
    first_name = user.get("first_name", "")
    return render_template("grep.html", first_name=first_name)


@app.route("/validate-image", methods=["POST"])
@login_required
def validate_image():
    """
    Server-side image validation matching VisionConfig:
      image_channels = 3  (RGB only)
      image_size     = 224 (resize handled client-side, we just verify it's a real image)
    """
    from PIL import Image
    import io

    file = request.files.get("image")
    if not file:
        return jsonify({"ok": False, "reason": "No image received."})

    try:
        img = Image.open(file.stream)
        img.verify()  # raises if the file is corrupt or not a real image
    except Exception:
        return jsonify({"ok": False, "reason": "File is not a valid image."})

    # Re-open after verify (verify() consumes the stream)
    file.stream.seek(0)
    img = Image.open(file.stream)

    if img.mode not in ("RGB", "L"):
        # Convert RGBA, P (palette), etc. — tell the client to use the JPEG version
        pass

    if img.mode != "RGB":
        return jsonify({"ok": False, "reason": f"Image must be RGB (got {img.mode}). Remove transparency and try again."})

    return jsonify({"ok": True})


@app.route("/chat", methods=["POST"])
@login_required
def chat():
    user_data   = request.json
    user_prompt = user_data.get("prompt", "")
    ai_response = greps_generate(user_prompt)
    return jsonify({"response": ai_response})


@app.route("/generate-title", methods=["POST"])
@login_required
def generate_title():
    data    = request.json
    message = data.get("message", "")
    if not message:
        return jsonify({"title": "New Chat"})
    title = greps_title(message)
    return jsonify({"title": title})




def admin_required(view):
    """Decorator that restricts a route to ADMIN_EMAIL only."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_email" not in session:
            return redirect(url_for("signin"))
        if session["user_email"] != ADMIN_EMAIL:
            # Authenticated but not admin — send home, not to signin
            return redirect(url_for("home"))
        return view(*args, **kwargs)
    return wrapped


def generate_threats(log: list) -> list:
    """Analyse the security log and produce categorised threat objects."""
    from collections import defaultdict
    ip_events = defaultdict(list)
    for event in log:
        if event.get("ip"):
            ip_events[event["ip"]].append(event)

    severity_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    threats = []
    counter = 0

    for ip, events in ip_events.items():
        failed   = [e for e in events if e["type"] == "failed_login"]
        blocked  = [e for e in events if e["type"] == "blocked_request"]
        n_failed = len(failed)
        n_blocked = len(blocked)

        if n_failed >= 10:
            sev, title = "CRITICAL", "Brute Force Attack"
            desc = f"{n_failed} failed login attempts from a single source"
            recs = ["Block source IP immediately", "Enable account lockout policy",
                    "Implement MFA", "Review all accounts targeted", "Enable rate limiting"]
        elif n_failed >= 5:
            sev, title = "HIGH", "Repeated Login Failures"
            desc = f"{n_failed} failed login attempts detected"
            recs = ["Block source IP", "Enable rate limiting", "Review targeted accounts"]
        elif n_blocked >= 5:
            sev, title = "HIGH", "Persistent Blocked Access"
            desc = f"Blocked IP still sending {n_blocked} requests"
            recs = ["Verify firewall rules are enforced", "Check for IP spoofing"]
        elif n_failed >= 2:
            sev, title = "MEDIUM", "Multiple Failed Logins"
            desc = f"{n_failed} failed login attempts"
            recs = ["Monitor IP for further activity", "Consider rate limiting"]
        elif n_failed == 1:
            sev, title = "LOW", "Failed Login Attempt"
            desc = "Single failed login attempt"
            recs = ["Monitor for repeat attempts"]
        else:
            continue

        counter += 1
        first_event = min(events, key=lambda e: e.get("timestamp", ""))
        geo = first_event.get("geo", {})
        geo_str = ""
        if geo.get("city") and geo.get("country"):
            geo_str = f"{geo['city']}, {geo['country']}"
        elif geo.get("country"):
            geo_str = geo["country"]

        threats.append({
            "id":           f"SEC-{counter:06d}",
            "title":        title,
            "description":  desc,
            "severity":     sev,
            "status":       "UNASSIGNED",
            "ip":           ip,
            "geo":          geo,
            "geo_str":      geo_str,
            "first_seen":   first_event.get("timestamp", ""),
            "total_events": len(events),
            "failed_logins": n_failed,
            "blocked_requests": n_blocked,
            "events":       list(reversed(events))[:20],
            "recommendations": recs,
        })

    threats.sort(key=lambda t: severity_order.get(t["severity"], 99))
    return threats


@app.route("/security")
@admin_required
def security():
    log      = list(reversed(load_security_log()))
    blocked  = load_blocked_ips()
    threats  = generate_threats(load_security_log())
    users    = load_users()
    return render_template("security.html",
                           log=log, blocked=blocked,
                           threats=threats, users=users,
                           admin_email=ADMIN_EMAIL)


@app.route("/security/block", methods=["POST"])
@admin_required
def block_ip():
    ip     = request.form.get("ip", "").strip()
    reason = request.form.get("reason", "Manually blocked").strip()
    if ip:
        blocked = load_blocked_ips()
        blocked[ip] = {
            "reason":     reason,
            "blocked_at": datetime.datetime.utcnow().isoformat(timespec="seconds") + "Z",
        }
        save_blocked_ips(blocked)
        log_event("ip_blocked", get_client_ip(), f"blocked {ip}: {reason}")
    return redirect(url_for("security"))


@app.route("/security/unblock", methods=["POST"])
@admin_required
def unblock_ip():
    ip = request.form.get("ip", "").strip()
    if ip:
        blocked = load_blocked_ips()
        blocked.pop(ip, None)
        save_blocked_ips(blocked)
        log_event("ip_unblocked", get_client_ip(), f"unblocked {ip}")
    return redirect(url_for("security"))


@app.route("/security/expire-account", methods=["POST"])
@admin_required
def expire_account():
    """Bump session_version so the user's current cookie becomes invalid."""
    email = request.form.get("email", "").strip().lower()
    if email and email != ADMIN_EMAIL:
        users = load_users()
        if email in users:
            users[email]["session_version"] = users[email].get("session_version", 0) + 1
            users[email].pop("force_logout", None)   # clean up old flag if present
            save_users(users)
            log_event("account_expired", get_client_ip(), f"session expired: {email}")
    return redirect(url_for("security"))


@app.route("/security/expire-all", methods=["POST"])
@admin_required
def expire_all_accounts():
    """Bump session_version for every non-admin account."""
    users = load_users()
    for email in users:
        if email != ADMIN_EMAIL:
            users[email]["session_version"] = users[email].get("session_version", 0) + 1
            users[email].pop("force_logout", None)
    save_users(users)
    log_event("accounts_expired_all", get_client_ip(), "expired all non-admin sessions")
    return redirect(url_for("security"))


@app.route("/security/delete-account", methods=["POST"])
@admin_required
def delete_account():
    email = request.form.get("email", "").strip().lower()
    if email and email != ADMIN_EMAIL:
        users = load_users()
        users.pop(email, None)
        save_users(users)
        log_event("account_deleted", get_client_ip(), f"deleted: {email}")
    return redirect(url_for("security"))


@app.route("/security/delete-all", methods=["POST"])
@admin_required
def delete_all_accounts():
    users = load_users()
    admin_data = users.get(ADMIN_EMAIL)
    new_users = {}
    if admin_data:
        new_users[ADMIN_EMAIL] = admin_data
    save_users(new_users)
    log_event("accounts_deleted_all", get_client_ip(), "deleted all non-admin accounts")
    return redirect(url_for("security"))


@app.errorhandler(404)
def page_not_found(error):
    redirect_url = url_for("home") if "user_email" in session else url_for("signin")
    return redirect(redirect_url)


if __name__ == "__main__":
    load_greps()
    app.run()
