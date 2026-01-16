# Datadog "Forbidden" Error - Complete Fix Guide

## The Problem
Your Application Key doesn't have "Actions API Access" enabled, even though you think you enabled it.

## Solution 1: Enable During Key Creation (MOST RELIABLE)

1. **Go to Datadog**: https://app.datadoghq.com
2. **Navigate**: Profile Icon (bottom left) → Organization Settings → Application Keys
3. **Delete the current key** (the one starting with `4f0b4590...`)
4. **Create NEW key**:
   - Click "New Key"
   - Name: "DataBone LLM - Full Access"
   - **BEFORE clicking "Create Key"**, look for "Actions API Access" toggle
   - **Enable it FIRST** (toggle ON)
   - **THEN click "Create Key"**
5. **Copy the key immediately** (you'll only see it once)
6. **Update `.env`**:
   ```bash
   DD_APP_KEY=the_new_key_you_just_copied
   ```
7. **Wait 1 minute**
8. **Test**: `python test_datadog_keys.py`

## Solution 2: Manual Dashboard Creation (WORKAROUND)

If Actions API Access keeps failing, create the dashboard manually:

1. **Go to Datadog**: https://app.datadoghq.com/dashboard
2. **Click "New Dashboard"**
3. **Name it**: "DataBone LLM Application - Observability Dashboard"
4. **Add widgets manually** (or use the JSON import if available)

This bypasses the API permission issue.

## Solution 3: Check Account Permissions

Your Datadog account might have restrictions:

1. **Check your role**: Profile Icon → My Profile
2. **Verify**: You should be "Admin" or "Standard User" (not "Read Only")
3. **If Read Only**: Ask your Datadog admin to upgrade your permissions

## Solution 4: Use Scoped Permissions Instead

Some Datadog accounts use scoped permissions instead of "Actions API Access":

1. **Go to**: Application Keys → Edit your key
2. **Look for "Scopes" section** (instead of "Actions API Access")
3. **Enable these scopes**:
   - `dashboards_write`
   - `monitors_write`
   - `dashboards_read`
   - `monitors_read`
4. **Save**

## Verification Steps

After enabling, verify:

1. **In Datadog UI**: Application Keys → Your key → Should show "Actions API Access: Enabled"
2. **In terminal**: Run `python test_datadog_keys.py`
3. **Expected output**:
   ```
   ✅ SUCCESS: Test monitor created (ID: ...)
   ✅ SUCCESS: Test dashboard created (ID: ...)
   ```

## Still Not Working?

Try this diagnostic:

1. **Check Datadog account type**: Free tier might have limitations
2. **Try a different browser**: Sometimes UI doesn't save properly
3. **Clear browser cache**: Old UI might be cached
4. **Contact Datadog support**: They can check your account permissions

## Quick Test Command

```bash
cd backend
python test_datadog_keys.py
```

If you see "Forbidden", the key still doesn't have write permissions.
