from time import time, sleep
from math import floor
import requests
import json
import os
import sys

# Global config
# location of log files
LOG_DIR = "/home/ec2-user/MinecraftServer/SpigotMC/logs"
# LOG_DIR = "."
LOG_PATH = f"{LOG_DIR}/latest.log"  # Spigot log file
PYTHON_LOG_PATH = f"{LOG_DIR}/log_handling.log"  # log file for this script
# max # of empty lines before logstream is closed and re-opened
MAX_EMPTY_BEFORE_CLOSE = 10
# amount of time to wait for retry if log file does not exist (yet) or if no
# updates to logfile are found
WAIT_TIME = 10
API_VERSION = "v1"  # current version of API (sort key for main table)
# base url for API
API_ENDPOINT = f"<endpoint url>/{API_VERSION}"
# headers to use for all request, mainly needs api key
HEADERS = {"x-api-key": "<api key>"}
LOG_FILE_BUFFER_TIME = 60  # number of seconds to give Spigot to create new log file


def get_users():
    """Returns dynamodb item for most recent login as python dict
    """
    print_log(f"Getting last login sessions for users...")
    endpoint = f"{API_ENDPOINT}/getLogins"
    response = requests.post(endpoint, headers=HEADERS)
    if str(response.content.decode("UTF-8")) == 'null' or str(response.status_code)[0] != '2':
        return []  # if this is a first time login, return empty list
    return json.loads(response.content.decode("UTF-8"))


def logout_user(username, login_time, version=API_VERSION):
    """Sets logout time for open login session
    """
    if version == API_VERSION:
        print_log(f"Marking user {username} as logged out...")
    endpoint = f"{API_ENDPOINT}/upsertLogin"
    data = json.dumps({'Username': username,
                       'Version': version,
                       'LoginTime': login_time,
                       'LogoutTime': floor(time())})
    response = requests.post(endpoint, headers=HEADERS, data=data)
    if str(response.status_code)[0] == '2':
        if version == API_VERSION:
            return logout_user(username, login_time, str(floor(time())))
        return get_last_login(username)
    return json.loads(response.content.decode("UTF-8").replace('null', 'None'))


def print_log(msg):
    """Print to console but also append to log file
    """
    print(msg)
    with open(PYTHON_LOG_PATH, 'a+') as s:
        s.write(msg + "\n")
        s.close()


def get_logged_out_user(line):
    """Parse out logged out user
        sample line:
            [00:20:19] [Server thread/INFO]: wooster2011 left the game
    """
    return line.split(' ')[3].strip()


def get_logged_in_user(line):
    """Parse out logged in user
        sample line:
            [00:20:08] [Server thread/INFO]: wooster2011[/99.144.124.104:54215]\
             logged in with entity id 1045 at ([world]3149.9607332168316, 68.0,\
              1324.5869047878969)
    """
    return line.split(' ')[3][:line.split(' ')[3].find('[')].strip()


def get_last_login(username):
    """Returns dynamodb item for most recent login as python dict
    """
    print_log(f"Getting last login session for {username}...")
    endpoint = f"{API_ENDPOINT}/getLogins"
    data = json.dumps({'Usernames': [username]})
    response = requests.post(endpoint, headers=HEADERS, data=data)
    if str(response.content.decode("UTF-8")) == 'null' or str(response.status_code)[0] != '2':
        return {}  # if this is a first time login, return nothing
    return json.loads(response.content.decode("UTF-8"))[0]


def log_new_login(username):
    """Creates new login for username on dynamodb table and returns new item as
       python dict
    """
    print_log(f"Marking user {username} as logged in...")
    endpoint = f"{API_ENDPOINT}/upsertLogin"
    data = json.dumps({'Username': username,
                       'Version': API_VERSION,
                       'LoginTime': floor(time()),
                       'LogoutTime': 0})
    response = requests.post(endpoint, headers=HEADERS, data=data)
    if str(response.status_code)[0] == '2':
        return get_last_login(username)
    print_log("Unknown error logging in: {}".format(
        response.content.decode("UTF-8")))
    return json.loads(response.content.decode("UTF-8").replace('null', 'None'))


def logout_user(username, login_time, version=API_VERSION):
    """Sets logout time for open login session
    """
    if version == API_VERSION:
        print_log(f"Marking user {username} as logged out...")
    endpoint = f"{API_ENDPOINT}/upsertLogin"
    data = json.dumps({'Username': username,
                       'Version': version,
                       'LoginTime': login_time,
                       'LogoutTime': floor(time())})
    response = requests.post(endpoint, headers=HEADERS, data=data)
    if str(response.status_code)[0] == '2':
        if version == API_VERSION:
            return logout_user(username, login_time, str(floor(time())))
        return get_last_login(username)
    return json.loads(response.content.decode("UTF-8").replace('null', 'None'))


def handle_login(line):
    """Either return object fo current user session (if not logged out) or
       create & return new login session (session = dynamodb item)
    """
    username = get_logged_in_user(line)
    print_log(f"User {username} has logged in")
    last_login = get_last_login(username)
    if last_login.get('LogoutTime') or not last_login.get('LoginTime'):
        print_log(f"New login for {username}...")
        return log_new_login(username)
    return last_login


def handle_logout(line):
    """Sets logout time for user, ending their session
    """
    username = get_logged_out_user(line)
    print_log(f"User {username} has logged out")
    last_login = get_last_login(username)
    if not last_login.get('LogoutTime'):
        return logout_user(username, last_login.get('LoginTime'))
    return last_login


def handle_server_start(line):
    print_log(f"Marking server as started...")
    endpoint = f"{API_ENDPOINT}/markStarted"
    response = requests.post(endpoint, headers=HEADERS)
    if str(response.status_code)[0] != '2':
        print_log("Failed to mark as started:",
                  response.content.decode("UTF-8"))
    return response.content.decode("UTF-8")


def handle_stop():
    print_log("Server stopping... marking any logged in users as logged out")
    users = get_users()
    count = 0
    for user in users:
        if not user.get('LogoutTime'):
            count += 1
            logout_user(user.get('Username'), user.get('LoginTime'))
    if count == 0:
        print_log("All users already logged out. No action taken.")
    sys.exit(0)


def handle_log(line):
    """ Do something with the log if it's something we care about. Usually do
        something means pushing to dynamodb table
    """
    if "[Server thread/INFO]: Done" in line and 'For help, type "help"' in line:
        handle_server_start(line)
    elif "logged in" in line:
        handle_login(line)
    elif "left the game" in line:
        handle_logout(line)
    elif "Stopping server" in line:
        handle_stop()


def new_logfile_created(content):
    """ Opens new logstream for logfile and validates if content is different
        from current logstream.
    """
    with open(LOG_PATH, 'r+') as s:
        if s.read() == content:
            return False
    return True


def track_logstream():
    """ Continually open & read log file. The log stream is closed and reopened
        whenever enough empty lines are hit and it's confirmed that a new 
        logfile appears to be created. This is to account for the "latest" 
        logfile being recreated by spigot.
    """
    try:
        print(f"Opening log file at {LOG_PATH}")
        s = open(LOG_PATH, 'r+')
    except FileNotFoundError:
        # wait preset # of seconds and try again if file does not exist (yet)
        print_log(
            f"Log path at {LOG_PATH} not found.. retrying in {WAIT_TIME}")
        sleep(WAIT_TIME)
        track_logstream()

    print_log("Tracking...")
    empty = 0
    content = ""
    while True:
        line = s.readline() or ""
        if not line:
            empty += 1
        else:
            content += line
        if empty >= MAX_EMPTY_BEFORE_CLOSE:
            if new_logfile_created(content):
                # close stream once empty line threshold is reached
                s.close()
                break
            else:
                # wait retry time and restart count
                # print_log(
                #     f"No new entries found, checking again in {WAIT_TIME}...")
                sleep(WAIT_TIME)
                empty = 0
        handle_log(line)
    print_log(f"Reopening log file at {LOG_PATH}...")
    track_logstream()  # reopen file


def main():
    time = os.path.getmtime(LOG_PATH)
    print_log("\n\n" + ("-" * 40) + "\n\n")
    print_log("Waiting for server to start...")
    time = os.path.getmtime(LOG_PATH)
    while True:
        sleep(LOG_FILE_BUFFER_TIME)
        if (time != os.path.getmtime(LOG_PATH)):
            track_logstream()
            sys.exit(1)


if __name__ == "__main__":
    main()
