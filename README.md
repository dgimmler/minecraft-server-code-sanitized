# Purpose

This repo represents a "sanitized" version of the minecraft server scripts. Mainly, sanitized here means the API keys and other URLs, IDs and IPs cleaned out.

This scrips were written out of practicality and not for learning purposes like other component sof the minecraft server app.

# Overview

This repo contains automation scripts that live and run directly on the EC2 instance running the minecraft server or otherwise run somewhere in the AWS account.

## capture_logins.py

Runs on EC2 instance and triggered as background job when server starts. Continuously tracks the server logs file, parses the logs and updates the user logins dynamodb table and server status accordingly.

## delete_snapshots.py

This script is triggered by in Event Bridge when the server stops. It cleans up any older snapshots we no longer need save costs. We limit the number of snapshots to 14 (lazy backup strategy).

## logout_users.py

Runs directly on EC2 instance. Triggered when server shuts down to run before shutdown. Mostly just calls the /logoutusers API endpoint to mark the logout times of any remaining users.
