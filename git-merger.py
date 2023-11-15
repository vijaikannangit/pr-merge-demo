#!/usr/bin/env python

"""This is the python module to process the pull request for merging.

This module takes below parameters.
pr -- Pull request url (Example: https://github.com/kumvijaya/pr-merge-demo/pull/1)
This performs below:
1. This connects to Github API, query the pull request with given pr url.
2. Checks the PR details whether it is mergeable (by checking the approvals and checks).
3. if the PR is mergeable, proceeds with merging.
"""

import requests
import os
import json
import argparse
from urllib.parse import urlparse

parser = argparse.ArgumentParser(
    description='Pull request merger'
)
parser.add_argument(
    '-p',
    '--pr',
    required=True,
    help='Provide PR URL e.g. https://github.com/kumvijaya/pr-merge-demo/pull/1')

args = parser.parse_args()
pr_url = args.pr
gh_token = os.environ["GITHUB_PASSWORD"]

def process_pr(pr_url):
    """process the pr by getting the pr data, validates and merges the PR inf required.

    Args:
        pr_url (str) : pr url ex: https://github.com/kumvijaya/pr-merge-demo/pull/1

    Returns:
        dict: pr data
    """
    pr_info = get_pr_info(pr_url)
    if not pr_info['already_merged']:
        if pr_info['approvals'] < pr_info['required_approvals']:
            raise Exception(f"No of approvals found in for the given pull request as {pr_info['approvals']}. The required number of approvers: ({pr_info['required_approvals']})")
        elif len(pr_info['failed_checks']) > 0:
            raise Exception(f"Required PR checks found failed ({pr_info['failed_checks']})")
        else:            
            merge_info = merge(pr_info)
            pr_info.update(merge_info)
    return pr_info

def get_pr_info(pr_url):
    """Gets the pr information for the given pr url

    Args:
        pr_url (str) : pr url ex: https://github.com/kumvijaya/pr-merge-demo/pull/1

    Returns:
        dict: pr data
    """
    pr_info = {}
    pr_url_info = get_pr_url_info(pr_url)
    pr_info.update(pr_url_info)
    pr = get_request(pr_info['pr_api_url'])
    pr_info['source_branch'] = pr['head']['ref']
    pr_info['target_branch'] = pr['base']['ref']
    pr_info['already_merged'] = pr['merged']
    pr_reviews_url = f"{pr_info['pr_api_url']}/reviews"
    pr_info.update(get_approval_info(pr_reviews_url))
    pr_info.update(get_checks_info(pr['statuses_url']))
    return pr_info

def get_pr_url_info(pr_url):
    """Gets pr url info 
    Parses the given url and gets the PR informtation

    Args:
        pr_url (str) : pr url ex: https://github.com/kumvijaya/pr-merge-demo/pull/1

    Returns:
        dict: PR Url info
    """
    url_info = {}
    pr_url_info = urlparse(pr_url)
    pr_path = pr_url_info.path.lstrip('/').rstrip('/').split("/")
    if len(pr_path) < 4:
        raise Exception(f"Invalid Pull request URL reeived : {pr_url}")
    url_info['org'] = pr_path[0]
    url_info['repo'] = pr_path[1]
    url_info['pr_number'] = pr_path[3]
    url_info['pr_api_url'] = f"https://api.github.com/repos/{url_info['org']}/{url_info['repo']}/pulls/{url_info['pr_number']}"
    url_info['pr_repo_url'] = f"https://github.com/{url_info['org']}/{url_info['repo']}.git"
    return url_info

def get_env_var_value(env_var, default_val=''):
    """Gets the env var value of the var 
    if given env var not exists, returns the given default value

    Args:
        env_var (str) : env var name
        default_val (str) : default value

    Returns:
        str: env var value
    """
    val = default_val
    if env_var in os.environ:
        val = os.environ[env_var]
    return val

def get_approval_info(pr_reviews_url):
    """Gets the PR approvals info. 
    Queries PR reviews and gets the approved reviews

    Args:
        pr_reviews_url (str) : reviews url

    Returns:
        dict: PR approvals info
    """
    approval_info = {}
    pr_reviews = get_request(pr_reviews_url)
    approved_reviews = [review for review in pr_reviews if review['state'] == "APPROVED"]
    approval_info['approvals'] = len(approved_reviews)
    approval_info['required_approvals'] = int(get_env_var_value('PR_MERGE_APPROVAL_COUNT', '2'))
    return approval_info
    
def get_checks_info(pr_checks_url):
    """Gets the PR checks statuses info

    Args:
        pr_checks_url (str) : request url

    Returns:
        dict: checks info
    """
    pr_checks = get_request(pr_checks_url)
    required_checks = get_env_var_value('PR_MERGE_STATUS_LABELS', '')
    checks_info = {}
    checks_info['failed_checks'] = []
    for required_check in required_checks:
        found_required_check = [check for check in pr_checks if check['context'] == required_check]
        if found_required_check and found_required_check['state'] != 'success':
            checks_info['failed_checks'].append(found_required_check)
    return checks_info

def get_reponse_json(resp, url, data=''):
    """Gets the reponse json

    Args:
        resp (obj) : response
        url (str) : request url
        data (str) : json data string

    Returns:
        dict: merge info
    """
    output = {}
    if is_success_status(resp.status_code):
        output = resp.json()
    else:
        resp_content = resp.content if resp.content else ""
        raise Exception(f"Error in api invocation {url}, data: {data}, status: {resp.status_code}, Response received: {resp_content}")
    return output

def get_request(url):
    """Gets github url reponse

    Args:
        url (str) : Github api url

    Returns:
        str: auth token
    """
    session = get_session(gh_token)
    resp = session.get(url)
    return get_reponse_json(resp, url)

def get_session(github_token):
    """Gets the requests session object by applying auth token

    Args:
        github_token (str): github token

    Returns:
        obj: requests session
    """
    session = requests.session()
    headers = {"Authorization": "token {}".format(github_token)}
    session.headers.update(headers)
    return session

def is_success_status(status_code):
    """checks given status code is success code.

    Args:
        status_code (int): http status code

    Returns:
        bool: is success status
    """
    return status_code in [200, 201, 202, 203, 204]

def put_request(url, data):
    """Invokes PUT request
    Args:
        url (str) : Github api url
        data (json) : json data
    """
    session = get_session(gh_token)
    resp = session.put(url, data)
    return get_reponse_json(resp, url, data)


def merge(pr_info):
    """Merges the pull request

    Args:
        pr_info (dict) : pr info

    Returns:
        dict: merge info
    """
    merge_info = {}
    url = f"{pr_info['pr_api_url']}/merge"
    body = {}
    body['commit_title'] = 'PR merged by PR Utility (Jenkins)'
    body['commit_message'] = 'PR merged by PR Utility (Jenkins) with required checks'
    merge_info = put_request(url, json.dumps(body))
    return merge_info


pr_info = process_pr(pr_url)
print(pr_info)
with open('git_merge_ouput.json', 'w') as fp:
    json.dump(pr_info, fp)