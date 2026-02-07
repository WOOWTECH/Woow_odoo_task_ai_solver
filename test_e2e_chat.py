#!/usr/bin/env python3
"""
End-to-end test for project_ai_solver module.
Tests: model fields, channel creation, security rules, portal API, two-way chat.
"""
import urllib.request
import urllib.parse
import json
import http.cookiejar
import sys

URL = "http://localhost:8069"
DB = "odoo18"
ADMIN_LOGIN = "admin"
ADMIN_PASS = "admin"
PORTAL_LOGIN = "portal"
PORTAL_PASS = "portal"

passed = 0
failed = 0


def log(status, msg):
    global passed, failed
    icon = "PASS" if status else "FAIL"
    if status:
        passed += 1
    else:
        failed += 1
    print(f"  [{icon}] {msg}")


def xmlrpc_call(model, method, args=None, kwargs=None, uid=None, password=None):
    """Make an XML-RPC call."""
    import xmlrpc.client
    if uid is None:
        common = xmlrpc.client.ServerProxy(f"{URL}/xmlrpc/2/common")
        uid = common.authenticate(DB, ADMIN_LOGIN, ADMIN_PASS, {})
        password = ADMIN_PASS
    models = xmlrpc.client.ServerProxy(f"{URL}/xmlrpc/2/object")
    return models.execute_kw(DB, uid, password, model, method, args or [], kwargs or {})


def make_session(login, password):
    """Create a JSON-RPC session."""
    cj = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    data = json.dumps({
        "jsonrpc": "2.0",
        "params": {"db": DB, "login": login, "password": password}
    }).encode()
    req = urllib.request.Request(
        f"{URL}/web/session/authenticate",
        data=data,
        headers={"Content-Type": "application/json"},
    )
    resp = opener.open(req)
    result = json.loads(resp.read())
    uid = result.get("result", {}).get("uid")
    return opener, uid


def json_rpc(opener, route, params):
    """Make a JSON-RPC call using a session."""
    data = json.dumps({"jsonrpc": "2.0", "params": params}).encode()
    req = urllib.request.Request(
        f"{URL}{route}",
        data=data,
        headers={"Content-Type": "application/json"},
    )
    resp = opener.open(req)
    result = json.loads(resp.read())
    if "error" in result:
        raise Exception(result["error"])
    return result.get("result")


# ============================================================
# TEST 1: Model fields exist
# ============================================================
print("\n=== TEST 1: Model Fields ===")
try:
    fields = xmlrpc_call("project.task", "fields_get", [["chat_enabled", "channel_id"]])
    log("chat_enabled" in fields, "chat_enabled field exists")
    log(fields.get("chat_enabled", {}).get("type") == "boolean", "chat_enabled is boolean")
    log("channel_id" in fields, "channel_id field exists")
    log(fields.get("channel_id", {}).get("type") == "many2one", "channel_id is many2one")
except Exception as e:
    log(False, f"fields_get failed: {e}")

# ============================================================
# TEST 2: Enable chat creates channel
# ============================================================
print("\n=== TEST 2: Channel Auto-Creation ===")
try:
    # Find a task with a customer assigned
    tasks = xmlrpc_call("project.task", "search_read",
                        [[["partner_id", "!=", False]]], {"fields": ["name", "partner_id", "chat_enabled", "channel_id"], "limit": 1})
    if tasks:
        task = tasks[0]
        task_id = task["id"]
        print(f"  Using task: {task['name']} (id={task_id})")

        # Disable chat first (reset)
        if task["channel_id"]:
            xmlrpc_call("project.task", "write", [[task_id], {"chat_enabled": False, "channel_id": False}])

        # Enable chat
        xmlrpc_call("project.task", "write", [[task_id], {"chat_enabled": True}])
        updated = xmlrpc_call("project.task", "read", [[task_id]], {"fields": ["chat_enabled", "channel_id"]})
        log(updated[0]["chat_enabled"] is True, "chat_enabled set to True")
        log(bool(updated[0]["channel_id"]), f"channel auto-created: {updated[0]['channel_id']}")
        channel_id = updated[0]["channel_id"][0] if updated[0]["channel_id"] else 0
    else:
        log(False, "No task with partner found")
        channel_id = 0
except Exception as e:
    log(False, f"Channel creation failed: {e}")
    channel_id = 0

# ============================================================
# TEST 3: Channel members
# ============================================================
print("\n=== TEST 3: Channel Members ===")
try:
    if channel_id:
        members = xmlrpc_call("discuss.channel.member", "search_read",
                              [[["channel_id", "=", channel_id]]], {"fields": ["partner_id"]})
        member_names = [m["partner_id"][1] for m in members]
        print(f"  Members: {member_names}")
        log(len(members) >= 1, f"Channel has {len(members)} member(s)")

        # Check portal user is a member
        portal_users = xmlrpc_call("res.users", "search_read",
                                   [[["login", "=", PORTAL_LOGIN]]], {"fields": ["partner_id"]})
        if portal_users:
            portal_partner_id = portal_users[0]["partner_id"][0]
            is_member = any(m["partner_id"][0] == portal_partner_id for m in members)
            log(is_member, f"Portal user is channel member")
        else:
            log(False, "Portal user not found")
    else:
        log(False, "No channel to check")
except Exception as e:
    log(False, f"Member check failed: {e}")

# ============================================================
# TEST 4: View inheritance
# ============================================================
print("\n=== TEST 4: View Inheritance ===")
try:
    result = xmlrpc_call("project.task", "get_view", [], {"view_type": "form"})
    arch = result.get("arch", "")
    log("chat_enabled" in arch, "chat_enabled in combined form view")
    log("task_chat_widget" in arch, "task_chat_widget in combined form view")
    log("chat_page" in arch, "Chat page tab in combined form view")
    log('w-100' in arch, "w-100 class in combined form view")
except Exception as e:
    log(False, f"View check failed: {e}")

# ============================================================
# TEST 5: Admin sends message via ORM
# ============================================================
print("\n=== TEST 5: Admin Sends Message ===")
try:
    if channel_id:
        xmlrpc_call("discuss.channel", "message_post", [[channel_id]], {
            "body": "Hello from admin!",
            "message_type": "comment",
            "subtype_xmlid": "mail.mt_comment",
        })
        msgs = xmlrpc_call("mail.message", "search_read", [[
            ["model", "=", "discuss.channel"],
            ["res_id", "=", channel_id],
            ["message_type", "=", "comment"],
        ]], {"fields": ["body", "author_id"], "order": "date desc", "limit": 1})
        log(len(msgs) > 0, "Admin message posted")
        log("Hello from admin" in (msgs[0].get("body", "") if msgs else ""), "Message body correct")
    else:
        log(False, "No channel for messaging")
except Exception as e:
    log(False, f"Admin message failed: {e}")

# ============================================================
# TEST 6: Portal user reads messages via API
# ============================================================
print("\n=== TEST 6: Portal Reads Messages ===")
try:
    if channel_id:
        portal_session, portal_uid = make_session(PORTAL_LOGIN, PORTAL_PASS)
        log(portal_uid is not None and portal_uid > 0, f"Portal login successful (uid={portal_uid})")

        result = json_rpc(portal_session, "/project_ai_solver/chat/history", {"channel_id": channel_id})
        msgs = result.get("messages", [])
        log(len(msgs) > 0, f"Portal loaded {len(msgs)} message(s)")
        admin_msg = any("Hello from admin" in (m.get("body", "") or "") for m in msgs)
        log(admin_msg, "Portal can see admin's message")
    else:
        log(False, "No channel for portal test")
except Exception as e:
    log(False, f"Portal read failed: {e}")

# ============================================================
# TEST 7: Portal user sends message via API
# ============================================================
print("\n=== TEST 7: Portal Sends Message ===")
try:
    if channel_id:
        result = json_rpc(portal_session, "/project_ai_solver/chat/post", {
            "channel_id": channel_id,
            "message_body": "Hello from portal user!",
        })
        log(result.get("success") is True, "Portal message post successful")

        # Verify message appears
        result = json_rpc(portal_session, "/project_ai_solver/chat/history", {"channel_id": channel_id})
        msgs = result.get("messages", [])
        portal_msg = any("Hello from portal" in (m.get("body", "") or "") for m in msgs)
        log(portal_msg, "Portal message visible in history")
    else:
        log(False, "No channel for portal send test")
except Exception as e:
    log(False, f"Portal send failed: {e}")

# ============================================================
# TEST 8: Admin sees portal's message
# ============================================================
print("\n=== TEST 8: Admin Sees Portal Message ===")
try:
    if channel_id:
        msgs = xmlrpc_call("mail.message", "search_read", [[
            ["model", "=", "discuss.channel"],
            ["res_id", "=", channel_id],
            ["message_type", "=", "comment"],
        ]], {"fields": ["body", "author_id"], "order": "date desc", "limit": 5})
        portal_msg = any("Hello from portal" in (m.get("body", "") or "") for m in msgs)
        log(portal_msg, "Admin can see portal user's message")
        print(f"  Total messages in channel: {len(msgs)}")
        for m in msgs:
            author = m.get("author_id", [0, "?"])[1]
            body = m.get("body", "")[:60]
            print(f"    - {author}: {body}")
    else:
        log(False, "No channel")
except Exception as e:
    log(False, f"Admin read failed: {e}")

# ============================================================
# TEST 9: Security - unauthorized portal access
# ============================================================
print("\n=== TEST 9: Security - Unauthorized Access ===")
try:
    # Try to access a channel that the portal user is NOT a member of
    # Create a fake channel_id that doesn't exist
    try:
        result = json_rpc(portal_session, "/project_ai_solver/chat/history", {"channel_id": 99999})
        log(False, "Should have denied access to non-existent channel")
    except Exception:
        log(True, "Access denied for non-existent channel")
except Exception as e:
    log(False, f"Security test failed: {e}")

# ============================================================
# TEST 10: Portal template values
# ============================================================
print("\n=== TEST 10: Portal Template ===")
try:
    # Check that the portal template exists and is correct
    import xmlrpc.client
    common = xmlrpc.client.ServerProxy(f"{URL}/xmlrpc/2/common")
    uid = common.authenticate(DB, ADMIN_LOGIN, ADMIN_PASS, {})
    models_proxy = xmlrpc.client.ServerProxy(f"{URL}/xmlrpc/2/object")

    views = models_proxy.execute_kw(DB, uid, ADMIN_PASS, "ir.ui.view", "search_read",
                                     [[["key", "=", "project_ai_solver.portal_my_task_chat"]]],
                                     {"fields": ["name", "active"]})
    log(len(views) > 0, f"Portal template exists: {views[0]['name'] if views else 'NOT FOUND'}")
    if views:
        log(views[0]["active"], "Portal template is active")
except Exception as e:
    log(False, f"Portal template check failed: {e}")

# ============================================================
# SUMMARY
# ============================================================
print(f"\n{'='*50}")
print(f"RESULTS: {passed} passed, {failed} failed, {passed+failed} total")
print(f"{'='*50}")
sys.exit(1 if failed > 0 else 0)
