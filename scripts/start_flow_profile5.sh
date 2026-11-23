#!/usr/bin/env bash
set -euo pipefail

# Launches Google Chrome (Profile 5) with CDP port 9222 in an isolated macOS user-data-dir
# (Required by Chrome 136+ on macOS, which blocks --remote-debugging-port on the default Chrome folder)

if curl -s http://127.0.0.1:9222/json/version >/dev/null 2>&1; then
  echo "Chrome CDP is already running on port 9222."
  exit 0
fi

node -e '
const fs = require("fs");
const os = require("os");
const path = require("path");
const { spawn } = require("child_process");

const chromePath = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const userDataSrc = path.join(os.homedir(), "Library/Application Support/Google/Chrome");
const profileName = process.env.FLOW_CHROME_PROFILE || "Profile 5";
const profileSrc = path.join(userDataSrc, profileName);
const tempDir = "/tmp/chrome-flow-profile5-cdp";

if (!fs.existsSync(tempDir)) {
  fs.mkdirSync(tempDir, { recursive: true });
  fs.cpSync(profileSrc, path.join(tempDir, profileName), {
    recursive: true,
    filter: (src) => !src.includes("/Cache") && !src.includes("/Code Cache") && !src.includes("/GPUCache") && !src.includes("Singleton")
  });
  if (fs.existsSync(path.join(userDataSrc, "Local State"))) {
    fs.cpSync(path.join(userDataSrc, "Local State"), path.join(tempDir, "Local State"));
  }
}

const p = spawn(chromePath, [
  "--remote-debugging-port=9222",
  `--user-data-dir=${tempDir}`,
  `--profile-directory=${profileName}`,
  "--no-first-run",
  "--no-default-browser-check",
  "--window-size=1920,1080",
  "https://flow.google.com/"
], { stdio: "ignore", detached: true });
p.unref();
console.log("Launched Chrome Profile 5 CDP (PID:", p.pid + ")");
'
