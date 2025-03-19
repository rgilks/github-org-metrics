import requests
import pandas as pd
from datetime import datetime, timedelta
import os
from collections import defaultdict
import time
import json
import argparse

# GitHub API configuration
GITHUB_API_URL = "https://api.github.com"
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
CACHE_FILE = "github_data_cache.json"

headers = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json"
}

def make_request(url):
    while True:
        try:
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 403 and 'X-RateLimit-Remaining' in response.headers and int(response.headers['X-RateLimit-Remaining']) == 0:
                reset_time = int(response.headers['X-RateLimit-Reset'])
                sleep_time = max(1, reset_time - time.time() + 1)  # Ensure sleep time is at least 1 second
                print(f"Rate limit exceeded. Sleeping for {sleep_time:.2f} seconds.")
                time.sleep(sleep_time)
            elif response.status_code == 403 and "Resource not accessible by personal access token" in response.text:
                print(f"Permission error for {url}: Your token doesn't have access to this resource.")
                return None
            elif response.status_code == 404 and "Not Found" in response.text:
                print(f"Resource not found for {url} - this is often normal for deleted branches.")
                return None
            else:
                print(f"Error fetching {url}: {response.status_code}")
                print(f"Response content: {response.text}")
                return None
        except requests.exceptions.RequestException as e:
            print(f"Request exception for {url}: {e}")
            return None

def get_org_repos(org, since, target_repos=None):
    repos = []
    page = 1
    
    # Keep track of which target repos we've found and which are still missing
    if target_repos:
        found_repos = set()
        missing_repos = set(target_repos)
    
    while True:
        url = f"{GITHUB_API_URL}/orgs/{org}/repos?page={page}&per_page=100&type=all&sort=pushed&direction=desc"
        print(f"Fetching: {url}")
        page_repos = make_request(url)
        if not page_repos:
            break
        
        # Filter repositories based on target_repos if provided
        if target_repos:
            filtered_repos = [repo for repo in page_repos if repo['name'] in target_repos and repo['pushed_at'] >= since]
            repos.extend(filtered_repos)
            
            # Update our tracking of found/missing repos
            newly_found = {repo['name'] for repo in filtered_repos}
            found_repos.update(newly_found)
            missing_repos -= newly_found
            
            print(f"Retrieved {len(filtered_repos)} specified repositories updated since {since}")
            
            # If we found all target repos or no more repos to check, exit
            if len(missing_repos) == 0 or len(page_repos) < 100:
                break
        else:
            # Original behavior: get top repos sorted by pushed_at
            repos.extend([repo for repo in page_repos if repo['pushed_at'] >= since])
            print(f"Retrieved {len(repos)} repositories updated since {since}")
            if len(page_repos) < 100 or len(repos) >= 20:
                break
        
        page += 1
    
    # Warn about any requested repos that weren't found
    if target_repos and missing_repos:
        print(f"WARNING: The following requested repositories were not found: {', '.join(missing_repos)}")
    
    # If no target repos specified, limit to 20 as in original code
    if not target_repos:
        return repos[:20]
    return repos

def get_commits(org, repo, since):
    commits = []
    page = 1
    while True:
        url = f"{GITHUB_API_URL}/repos/{org}/{repo}/commits?since={since}&page={page}&per_page=100"
        page_commits = make_request(url)
        if not page_commits:
            break
        commits.extend(page_commits)
        if len(page_commits) < 100:
            break
        page += 1
    print(f"Total commits for {repo}: {len(commits)}")
    return commits

def get_commit_stats(org, repo, sha):
    url = f"{GITHUB_API_URL}/repos/{org}/{repo}/commits/{sha}"
    commit_data = make_request(url)
    if commit_data and 'stats' in commit_data:
        return commit_data['stats']
    return None

def get_branches(org, repo):
    url = f"{GITHUB_API_URL}/repos/{org}/{repo}/branches"
    return make_request(url)

def get_contributors(org, repo):
    url = f"{GITHUB_API_URL}/repos/{org}/{repo}/contributors"
    return make_request(url)

def get_pull_requests(org, repo, state='all'):
    pull_requests = []
    page = 1
    while True:
        url = f"{GITHUB_API_URL}/repos/{org}/{repo}/pulls?state={state}&page={page}&per_page=100"
        page_prs = make_request(url)
        if not page_prs:
            break
        pull_requests.extend(page_prs)
        if len(page_prs) < 100:
            break
        page += 1
    print(f"Total pull requests for {repo}: {len(pull_requests)}")
    return pull_requests

def get_pull_request_reviews(org, repo, pr_number):
    url = f"{GITHUB_API_URL}/repos/{org}/{repo}/pulls/{pr_number}/reviews"
    return make_request(url)

def get_pull_request_comments(org, repo, pr_number):
    url = f"{GITHUB_API_URL}/repos/{org}/{repo}/pulls/{pr_number}/comments"
    return make_request(url)

def get_branch_commits(org, repo, branch):
    try:
        url = f"{GITHUB_API_URL}/repos/{org}/{repo}/commits?sha={branch}&per_page=100"
        commits = make_request(url)
        if commits and len(commits) > 0:
            # Return the oldest commit (last in the list if sorted newest first)
            return commits[-1]
        return None
    except Exception as e:
        print(f"Error getting commits for {repo}/{branch}: {e}")
        return None

def get_workflow_runs(org, repo):
    url = f"{GITHUB_API_URL}/repos/{org}/{repo}/actions/runs?per_page=100"
    return make_request(url)

def get_workflow_run_details(org, repo, run_id):
    url = f"{GITHUB_API_URL}/repos/{org}/{repo}/actions/runs/{run_id}"
    return make_request(url)
    
def get_workflow_by_name(org, repo, workflow_name):
    url = f"{GITHUB_API_URL}/repos/{org}/{repo}/actions/workflows/{workflow_name}.yml"
    workflow = make_request(url)
    if not workflow:
        url = f"{GITHUB_API_URL}/repos/{org}/{repo}/actions/workflows/{workflow_name}.yaml"
        workflow = make_request(url)
    return workflow

def get_deployments(org, repo):
    url = f"{GITHUB_API_URL}/repos/{org}/{repo}/deployments?per_page=100"
    return make_request(url)

def get_releases(org, repo):
    url = f"{GITHUB_API_URL}/repos/{org}/{repo}/releases?per_page=100"
    return make_request(url)

def get_tags(org, repo):
    url = f"{GITHUB_API_URL}/repos/{org}/{repo}/tags?per_page=100"
    return make_request(url)

def get_issues(org, repo, state='all'):
    issues = []
    page = 1
    while True:
        url = f"{GITHUB_API_URL}/repos/{org}/{repo}/issues?state={state}&page={page}&per_page=100"
        page_issues = make_request(url)
        if not page_issues:
            break
        # Filter out pull requests, which are also returned by the issues endpoint
        issues.extend([issue for issue in page_issues if 'pull_request' not in issue])
        if len(page_issues) < 100:
            break
        page += 1
    print(f"Total issues for {repo}: {len(issues)}")
    return issues

def fetch_data(org, since, target_repos=None):
    data = {
        'repos': get_org_repos(org, since, target_repos),
        'commits': {},
        'commit_stats': {},
        'branches': {},
        'contributors': {},
        'pull_requests': {},
        'pr_reviews': {},
        'pr_comments': {},
        'branch_first_commits': {},  # Store first commit for each branch
        # Additional DORA-related data
        'workflow_runs': {},
        'workflow_run_details': {},  # Store details for each workflow run
        'deployments': {},
        'releases': {},
        'tags': {},
        'issues': {}
    }
    
    for repo in data['repos']:
        repo_name = repo['name']
        print(f"Fetching detailed data for {repo_name}")
        data['commits'][repo_name] = get_commits(org, repo_name, since)
        data['commit_stats'][repo_name] = {}
        for commit in data['commits'][repo_name]:
            data['commit_stats'][repo_name][commit['sha']] = get_commit_stats(org, repo_name, commit['sha'])
        data['branches'][repo_name] = get_branches(org, repo_name)
        data['contributors'][repo_name] = get_contributors(org, repo_name)
        data['pull_requests'][repo_name] = get_pull_requests(org, repo_name)
        data['pr_reviews'][repo_name] = {}
        data['pr_comments'][repo_name] = {}
        data['branch_first_commits'][repo_name] = {}
        
        # Collect additional DORA-related data
        print(f"Fetching DORA-related data for {repo_name}")
        try:
            data['workflow_runs'][repo_name] = get_workflow_runs(org, repo_name)
            
            # Get detailed info for each workflow run
            if data['workflow_runs'][repo_name] and 'workflow_runs' in data['workflow_runs'][repo_name]:
                data['workflow_run_details'][repo_name] = {}
                
                for run in data['workflow_runs'][repo_name]['workflow_runs']:
                    # Only fetch details for completed runs 
                    if run['status'] == 'completed':
                        run_id = run['id']
                        data['workflow_run_details'][repo_name][run_id] = get_workflow_run_details(org, repo_name, run_id)
            
            print(f"  - Fetched {len(data['workflow_runs'][repo_name].get('workflow_runs', []) or [])} workflow runs")
        except Exception as e:
            print(f"  - Error fetching workflow runs: {e}")
            data['workflow_runs'][repo_name] = []
            data['workflow_run_details'][repo_name] = {}
            
        try:
            data['deployments'][repo_name] = get_deployments(org, repo_name)
            print(f"  - Fetched {len(data['deployments'][repo_name] or [])} deployments")
        except Exception as e:
            print(f"  - Error fetching deployments: {e}")
            data['deployments'][repo_name] = []
            
        try:
            data['releases'][repo_name] = get_releases(org, repo_name)
            print(f"  - Fetched {len(data['releases'][repo_name] or [])} releases")
        except Exception as e:
            print(f"  - Error fetching releases: {e}")
            data['releases'][repo_name] = []
            
        try:
            data['tags'][repo_name] = get_tags(org, repo_name)
            print(f"  - Fetched {len(data['tags'][repo_name] or [])} tags")
        except Exception as e:
            print(f"  - Error fetching tags: {e}")
            data['tags'][repo_name] = []
            
        try:
            data['issues'][repo_name] = get_issues(org, repo_name)
            print(f"  - Fetched {len(data['issues'][repo_name] or [])} issues")
        except Exception as e:
            print(f"  - Error fetching issues: {e}")
            data['issues'][repo_name] = []
            
        # Process PR data to get branch information
        processed_prs = 0
        total_prs = len(data['pull_requests'][repo_name])
        print(f"Processing {total_prs} PRs for {repo_name}...")
        
        # Count open PRs (branches that still exist)
        open_prs_count = sum(1 for pr in data['pull_requests'][repo_name] if pr.get('state') == 'open')
        print(f"  - Found {open_prs_count} open PRs with existing branches")
            
        for pr in data['pull_requests'][repo_name]:
            pr_number = pr['number']
            processed_prs += 1
            if processed_prs % 10 == 0:
                print(f"  - Processed {processed_prs}/{total_prs} PRs")
                
            data['pr_reviews'][repo_name][pr_number] = get_pull_request_reviews(org, repo_name, pr_number)
            data['pr_comments'][repo_name][pr_number] = get_pull_request_comments(org, repo_name, pr_number)
            
            # Only look for branch commits for open PRs - merged PR branches are deleted
            if pr.get('state') == 'open' and 'head' in pr and 'ref' in pr['head']:
                branch_name = pr['head']['ref']
                try:
                    data['branch_first_commits'][repo_name][branch_name] = get_branch_commits(org, repo_name, branch_name)
                    if data['branch_first_commits'][repo_name][branch_name]:
                        if processed_prs % 10 == 0:
                            print(f"    Found first commit for {repo_name}/{branch_name}")
                except Exception as e:
                    data['branch_first_commits'][repo_name][branch_name] = None
            # For merged PRs, we won't try to fetch branch commits since branches are deleted
            elif pr.get('state') == 'closed' and pr.get('merged_at') and 'head' in pr and 'ref' in pr['head']:
                # If the branch was merged, we'll estimate branch start from PR creation time
                # or if available, the first commit timestamp in the PR
                branch_name = pr['head']['ref']
                
                # Initialize with a placeholder - we'll use PR creation date as fallback
                data['branch_first_commits'][repo_name][branch_name] = {
                    'commit': {
                        'committer': {
                            'date': pr['created_at']
                        }
                    }
                }
    
    return data

def analyze_data(data, since):
    commit_counts = defaultdict(int)
    lines_added = defaultdict(int)
    lines_deleted = defaultdict(int)
    repos_worked_on = defaultdict(lambda: defaultdict(int))
    repo_activity = defaultdict(int)
    repo_details = []
    
    pr_counts = defaultdict(int)
    pr_reviews = defaultdict(int)
    pr_comments = defaultdict(int)
    pr_merge_times = []  # PR creation to merge
    branch_to_merge_times = []  # Branch creation/first commit to merge
    repo_branch_to_merge_times = defaultdict(list)  # Track branch-to-merge times per repository
    branch_lifetimes = []
    
    # DORA metrics data structures
    repo_deployment_counts = defaultdict(int)
    repo_deployment_failures = defaultdict(int)
    repo_deployment_recovery_times = defaultdict(list)
    
    # GitHub Actions deployment metrics
    repo_deployment_durations = defaultdict(list)  # Track deployment durations per repository
    
    # Debug counters
    total_prs_processed = 0
    total_reviews_found = 0
    total_comments_found = 0
    
    # Get the list of repositories we're analyzing
    repo_names = [repo['name'] for repo in data['repos']]
    
    # Process GitHub Actions workflow runs
    # Instead of hardcoding repository names, detect workflows in all repositories we're analyzing
    specific_workflows = {}
    
    # Try to detect CI/CD workflows in each repo
    for repo_name in repo_names:
        if repo_name in data['workflow_runs']:
            workflows = data['workflow_runs'][repo_name]
            if workflows and 'workflow_runs' in workflows and len(workflows['workflow_runs']) > 0:
                # Find the most common workflow name in this repo
                workflow_names = [run['name'].lower() for run in workflows['workflow_runs'] 
                                if 'name' in run and run['name']]
                
                # Look for CI/CD related workflow names
                ci_workflows = [name for name in workflow_names 
                              if 'ci' in name or 'test' in name or 'build' in name or 'deploy' in name]
                
                if ci_workflows:
                    # Count occurrences of each CI workflow name
                    from collections import Counter
                    workflow_counter = Counter(ci_workflows)
                    # Get the most common CI workflow name
                    most_common = workflow_counter.most_common(1)
                    if most_common:
                        specific_workflows[repo_name] = most_common[0][0]
                        print(f"Detected workflow '{most_common[0][0]}' for {repo_name}")
                else:
                    # If no CI/CD specific workflows found, use the most common workflow
                    if workflow_names:
                        from collections import Counter
                        workflow_counter = Counter(workflow_names)
                        most_common = workflow_counter.most_common(1)
                        if most_common:
                            specific_workflows[repo_name] = most_common[0][0]
                            print(f"No CI/CD workflow found, using most common workflow '{most_common[0][0]}' for {repo_name}")
    
    # Fix: Pre-count all PR reviews and comments by user
    for repo_name in data['pr_reviews']:
        # Skip repositories not in our analysis set
        if repo_name not in repo_names:
            continue
            
        for pr_number in data['pr_reviews'][repo_name]:
            pr_reviews_list = data['pr_reviews'][repo_name].get(pr_number, []) or []
            for review in pr_reviews_list:
                if review and review.get('user') and 'login' in review['user']:
                    # Filter reviews by date
                    if 'submitted_at' in review:
                        review_date = datetime.strptime(review['submitted_at'], "%Y-%m-%dT%H:%M:%SZ").isoformat()
                        if review_date >= since:
                            reviewer = review['user']['login']
                            pr_reviews[reviewer] += 1
                            total_reviews_found += 1
    
    for repo_name in data['pr_comments']:
        # Skip repositories not in our analysis set
        if repo_name not in repo_names:
            continue
            
        for pr_number in data['pr_comments'][repo_name]:
            pr_comments_list = data['pr_comments'][repo_name].get(pr_number, []) or []
            for comment in pr_comments_list:
                if comment and comment.get('user') and 'login' in comment['user']:
                    # Filter comments by date
                    if 'created_at' in comment:
                        comment_date = datetime.strptime(comment['created_at'], "%Y-%m-%dT%H:%M:%SZ").isoformat()
                        if comment_date >= since:
                            commenter = comment['user']['login']
                            pr_comments[commenter] += 1
                            total_comments_found += 1

    # Process workflow data for DORA metrics
    for repo_name in repo_names:
        # Process workflows to calculate deployment stats
        if repo_name in specific_workflows and repo_name in data['workflow_runs']:
            target_workflow_name = specific_workflows[repo_name]
            deployment_count = 0
            failure_count = 0
            
            if 'workflow_runs' in data['workflow_runs'][repo_name]:
                for run in data['workflow_runs'][repo_name]['workflow_runs']:
                    if 'created_at' in run and 'name' in run and run['name'].lower() == target_workflow_name:
                        # Only consider runs created after our since date
                        run_created_at = datetime.strptime(run['created_at'], "%Y-%m-%dT%H:%M:%SZ").isoformat()
                        if run_created_at >= since:
                            # Count this as a deployment attempt regardless of success/failure
                            deployment_count += 1
                            
                            if run['conclusion'] == 'success':
                                # Calculate deployment duration for successful runs
                                if 'created_at' in run and 'updated_at' in run:
                                    created_at = datetime.strptime(run['created_at'], "%Y-%m-%dT%H:%M:%SZ")
                                    completed_at = datetime.strptime(run['updated_at'], "%Y-%m-%dT%H:%M:%SZ")
                                    duration_minutes = (completed_at - created_at).total_seconds() / 60
                                    repo_deployment_durations[repo_name].append(duration_minutes)
                            elif run['conclusion'] == 'failure':
                                # Count failures (already counted in deployment_count)
                                failure_count += 1
            
            repo_deployment_counts[repo_name] = deployment_count
            repo_deployment_failures[repo_name] = failure_count
            
    print(f"DEBUG: Pre-counted {total_reviews_found} reviews ({len(pr_reviews)} reviewers)")
    print(f"DEBUG: Pre-counted {total_comments_found} comments ({len(pr_comments)} commenters)")
    
    for repo in data['repos']:
        repo_name = repo['name']
        repo_detail = {
            'name': repo_name,
            'created_at': datetime.strptime(repo['created_at'], "%Y-%m-%dT%H:%M:%SZ").strftime("%B %d, %Y"),
            'updated_at': datetime.strptime(repo['updated_at'], "%Y-%m-%dT%H:%M:%SZ").strftime("%B %d, %Y"),
            'language': repo['language'] or 'N/A',
            'branch_count': len(data['branches'][repo_name]),
            'contributor_count': len(data['contributors'][repo_name]),
            # DORA metrics
            'deployment_count': repo_deployment_counts.get(repo_name, 0),
            'deployment_failures': repo_deployment_failures.get(repo_name, 0),
            'avg_recovery_time': (sum(repo_deployment_recovery_times.get(repo_name, [0])) / len(repo_deployment_recovery_times.get(repo_name, [0]))) if repo_deployment_recovery_times.get(repo_name) else 0,
            # GitHub Actions metrics
            'avg_deployment_duration': (sum(repo_deployment_durations.get(repo_name, [0])) / len(repo_deployment_durations.get(repo_name, [0]))) if repo_deployment_durations.get(repo_name) else 0,
            'deployment_durations_count': len(repo_deployment_durations.get(repo_name, [])),
        }
        
        # Calculate deployment failure rate
        if repo_detail['deployment_count'] > 0:
            repo_detail['failure_rate'] = (repo_detail['deployment_failures'] / repo_detail['deployment_count']) * 100
        else:
            repo_detail['failure_rate'] = 0
            
        repo_details.append(repo_detail)
        
        for commit in data['commits'][repo_name]:
            if commit['commit']['author']['date'] >= since:
                if commit['author'] and 'login' in commit['author']:
                    author = commit['author']['login']
                    commit_counts[author] += 1
                    repos_worked_on[author][repo_name] += 1
                    repo_activity[repo_name] += 1
                    
                    stats = data['commit_stats'][repo_name].get(commit['sha'])
                    if stats:
                        lines_added[author] += stats['additions']
                        lines_deleted[author] += stats['deletions']
        
        pr_merge_times_for_repo = []
        branch_to_merge_times_for_repo = []
        
        for pr in data['pull_requests'][repo_name]:
            if pr['user'] and 'login' in pr['user']:
                pr_number = pr['number']
                
                # Only count PRs created or updated within the time period
                pr_created_at = datetime.strptime(pr['created_at'], "%Y-%m-%dT%H:%M:%SZ").isoformat()
                pr_updated_at = datetime.strptime(pr['updated_at'], "%Y-%m-%dT%H:%M:%SZ").isoformat()
                
                # Only include PRs that were created or updated since the specified date
                if pr_created_at >= since or pr_updated_at >= since:
                    author = pr['user']['login']
                    pr_counts[author] += 1
                    
                    if pr['merged_at']:
                        created_at = datetime.strptime(pr['created_at'], "%Y-%m-%dT%H:%M:%SZ")
                        merged_at = datetime.strptime(pr['merged_at'], "%Y-%m-%dT%H:%M:%SZ")
                        
                        # Track traditional PR creation to merge time
                        if pr_created_at >= since and pr['merged_at'] >= since:
                            merge_time_hours = (merged_at - created_at).total_seconds() / 3600  # in hours
                            
                            # Filter out extreme outliers (PRs that took more than 30 days to merge)
                            if merge_time_hours <= 30 * 24:  # 30 days in hours
                                pr_merge_times.append(merge_time_hours)
                                pr_merge_times_for_repo.append(merge_time_hours)
                            else:
                                print(f"Excluding outlier PR #{pr_number} in {repo_name} with merge time of {merge_time_hours:.2f} hours")
                        
                        # Now calculate branch creation to merge time
                        branch_name = pr['head']['ref'] if 'head' in pr and 'ref' in pr['head'] else None
                        
                        if branch_name and branch_name in data['branch_first_commits'].get(repo_name, {}):
                            first_commit = data['branch_first_commits'][repo_name][branch_name]
                            if first_commit and 'commit' in first_commit and 'committer' in first_commit['commit'] and 'date' in first_commit['commit']['committer']:
                                # Get the timestamp of the first commit
                                branch_start_date = datetime.strptime(first_commit['commit']['committer']['date'], "%Y-%m-%dT%H:%M:%SZ")
                                
                                # Calculate how long from first commit to merge
                                branch_to_merge_time = (merged_at - branch_start_date).total_seconds() / 3600  # in hours
                                
                                # Filter out extreme outliers
                                if branch_to_merge_time <= 90 * 24:  # 90 days in hours - branches can live longer than PRs
                                    branch_to_merge_times.append(branch_to_merge_time)
                                    branch_to_merge_times_for_repo.append(branch_to_merge_time)
                                else:
                                    print(f"Excluding outlier branch {branch_name} in {repo_name} with lifetime of {branch_to_merge_time:.2f} hours")
                
                total_prs_processed += 1
                
        # Store the merge times for this repo
        repo_branch_to_merge_times[repo_name] = branch_to_merge_times_for_repo
        
        if branch_to_merge_times_for_repo:
            print(f"Branch-to-merge times for {repo_name}: min={min(branch_to_merge_times_for_repo):.2f}h, max={max(branch_to_merge_times_for_repo):.2f}h, avg={sum(branch_to_merge_times_for_repo)/len(branch_to_merge_times_for_repo):.2f}h, count={len(branch_to_merge_times_for_repo)}")
        else:
            print(f"No valid branch-to-merge time data for {repo_name}")

    print(f"DEBUG: Processed {total_prs_processed} PRs")
    print(f"DEBUG: Found {total_reviews_found} reviews during analysis")
    print(f"DEBUG: Found {total_comments_found} comments during analysis")
    print(f"DEBUG: PR Reviews counter has {sum(pr_reviews.values())} entries")
    print(f"DEBUG: PR Comments counter has {sum(pr_comments.values())} entries")

    # Calculate average branch-to-merge time per repository
    repo_avg_branch_to_merge_times = {}
    for repo_name, merge_times in repo_branch_to_merge_times.items():
        if merge_times:
            repo_avg_branch_to_merge_times[repo_name] = sum(merge_times) / len(merge_times)
        else:
            repo_avg_branch_to_merge_times[repo_name] = 0

    def format_repos(repos_dict):
        sorted_repos = sorted(repos_dict.items(), key=lambda x: x[1], reverse=True)
        if len(sorted_repos) <= 5:
            return ', '.join(repo for repo, _ in sorted_repos)
        else:
            top_5 = ', '.join(repo for repo, _ in sorted_repos[:5])
            remaining = len(sorted_repos) - 5
            return f"{top_5} +{remaining} more"

    df_developers = pd.DataFrame({
        'Developer': list(set(list(commit_counts.keys()) + list(pr_reviews.keys()) + list(pr_comments.keys()))),
        'Commits': [commit_counts.get(dev, 0) for dev in set(list(commit_counts.keys()) + list(pr_reviews.keys()) + list(pr_comments.keys()))],
        'Lines Added': [lines_added.get(dev, 0) for dev in set(list(commit_counts.keys()) + list(pr_reviews.keys()) + list(pr_comments.keys()))],
        'Lines Deleted': [lines_deleted.get(dev, 0) for dev in set(list(commit_counts.keys()) + list(pr_reviews.keys()) + list(pr_comments.keys()))],
        'PRs Opened': [pr_counts.get(dev, 0) for dev in set(list(commit_counts.keys()) + list(pr_reviews.keys()) + list(pr_comments.keys()))],
        'PRs Reviewed': [pr_reviews.get(dev, 0) for dev in set(list(commit_counts.keys()) + list(pr_reviews.keys()) + list(pr_comments.keys()))],
        'PR Comments': [pr_comments.get(dev, 0) for dev in set(list(commit_counts.keys()) + list(pr_reviews.keys()) + list(pr_comments.keys()))],
        'Repositories': [format_repos(repos_worked_on.get(dev, {})) for dev in set(list(commit_counts.keys()) + list(pr_reviews.keys()) + list(pr_comments.keys()))]
    })

    df_developers = df_developers.sort_values('Commits', ascending=False)

    # Add average branch-to-merge time to repo details
    for repo in repo_details:
        repo['avg_branch_to_merge_time'] = repo_avg_branch_to_merge_times.get(repo['name'], 0)
        repo['branch_merges_count'] = len(repo_branch_to_merge_times.get(repo['name'], []))

    df_repos = pd.DataFrame(repo_details)
    df_repos['Activity'] = df_repos['name'].map(repo_activity)
    df_repos = df_repos[['name', 'Activity', 'avg_branch_to_merge_time', 'branch_merges_count', 
                          'deployment_count', 'failure_rate', 'avg_recovery_time', 'avg_deployment_duration', 'deployment_durations_count',
                          'created_at', 'updated_at', 'language', 'branch_count', 'contributor_count']]
    df_repos = df_repos.sort_values('Activity', ascending=False)

    # Calculate overall averages - only for repositories in our analysis set
    avg_pr_merge_time = sum(pr_merge_times) / len(pr_merge_times) if pr_merge_times else 0
    avg_branch_to_merge_time = sum(branch_to_merge_times) / len(branch_to_merge_times) if branch_to_merge_times else 0

    # Format the DataFrames for better readability
    pd.set_option('display.max_colwidth', None)
    
    developer_formatters = {
        'Developer': lambda x: f'{x:<20}',
        'Commits': lambda x: f'{x:>7}',
        'Lines Added': lambda x: f'{x:>11}',
        'Lines Deleted': lambda x: f'{x:>13}',
        'PRs Opened': lambda x: f'{x:>10}',
        'PRs Reviewed': lambda x: f'{x:>12}',
        'PR Comments': lambda x: f'{x:>11}',
        'Repositories': lambda x: f'{x}'
    }

    repo_formatters = {
        'name': lambda x: f'{x:<30}',
        'Activity': lambda x: f'{x:>8}',
        'avg_branch_to_merge_time': lambda x: f'{x:>24.2f}',
        'branch_merges_count': lambda x: f'{x:>19}',
        'deployment_count': lambda x: f'{x:>16}',
        'failure_rate': lambda x: f'{x:>12.2f}%',
        'avg_recovery_time': lambda x: f'{x:>17.2f}',
        'avg_deployment_duration': lambda x: f'{x:>22.2f}',
        'deployment_durations_count': lambda x: f'{x:>24}',
        'created_at': lambda x: f'{x:>20}',
        'updated_at': lambda x: f'{x:>20}',
        'language': lambda x: f'{x:<10}',
        'branch_count': lambda x: f'{x:>12}',
        'contributor_count': lambda x: f'{x:>18}'
    }

    # Information about which repositories are included in the analysis
    analyzed_repos = ", ".join([repo for repo in repo_names])
    
    print("\nFinal Results:")
    print(f"Analyzed Repositories: {analyzed_repos}")
    print(f"Total Repositories Processed: {len(data['repos'])}")
    print(f"\nAverage PR Merge Time (from PR creation): {avg_pr_merge_time:.2f} hours")
    print(f"Average Branch-to-Merge Time (from first commit): {avg_branch_to_merge_time:.2f} hours")
    print("\nDeveloper Activity:")
    print(df_developers.to_string(index=False, formatters=developer_formatters, justify='left'))
    print("\nRepository Details:")
    print(df_repos.to_string(index=False, formatters=repo_formatters, justify='left'))

    # Add a DORA metrics summary to the final output - only for repositories in our analysis set
    print("\nDORA Metrics Summary:")
    print(f"Lead Time (Branch to Merge): {avg_branch_to_merge_time:.2f} hours")
    
    # Add GitHub Actions deployment duration summary - only for analyzed repositories
    deployment_durations_for_analyzed_repos = []
    for repo_name in repo_names:
        if repo_name in repo_deployment_durations:
            deployment_durations_for_analyzed_repos.extend(repo_deployment_durations[repo_name])
            
    if deployment_durations_for_analyzed_repos:
        avg_deployment_duration = sum(deployment_durations_for_analyzed_repos) / len(deployment_durations_for_analyzed_repos)
        print(f"Average Deployment Duration: {avg_deployment_duration:.2f} minutes")
    else:
        print(f"Average Deployment Duration: No data available")
    
    # Calculate average deployment frequency (per week per repo) - only for analyzed repositories
    try:
        # Try different date formats to handle variations in the 'since' format
        try:
            since_date = datetime.strptime(since, "%Y-%m-%dT%H:%M:%S.%f")
        except ValueError:
            try:
                since_date = datetime.strptime(since, "%Y-%m-%dT%H:%M:%S")
            except ValueError:
                since_date = datetime.strptime(since, "%Y-%m-%d")
                
        weeks_in_period = (datetime.now() - since_date).days / 7
        
        # Only count deployment data for our analyzed repositories
        total_deployments_in_analyzed_repos = sum(repo_deployment_counts[repo_name] for repo_name in repo_names)
        active_repos = sum(1 for repo_name in repo_names if repo_deployment_counts[repo_name] > 0)
        
        if active_repos > 0 and weeks_in_period > 0:
            avg_deployments_per_week = total_deployments_in_analyzed_repos / (active_repos * weeks_in_period)
            print(f"Deployment Frequency: {avg_deployments_per_week:.2f} deployments per week per active repo")
        else:
            print("Deployment Frequency: No active repositories with deployments in the time period")
    except Exception as e:
        print(f"Error calculating deployment frequency: {e}")
    
    # Calculate overall failure rate - only for analyzed repositories
    total_deployments = sum(repo_deployment_counts[repo_name] for repo_name in repo_names)
    total_failures = sum(repo_deployment_failures[repo_name] for repo_name in repo_names)
    
    if total_deployments > 0:
        overall_failure_rate = (total_failures / total_deployments) * 100
        print(f"Change Failure Rate: {overall_failure_rate:.2f}%")
    else:
        print(f"Change Failure Rate: No deployment data available")
    
    # Calculate average recovery time - only for analyzed repositories
    recovery_times_for_analyzed_repos = []
    for repo_name in repo_names:
        if repo_name in repo_deployment_recovery_times:
            recovery_times_for_analyzed_repos.extend(repo_deployment_recovery_times[repo_name])
            
    if recovery_times_for_analyzed_repos:
        avg_recovery_time = sum(recovery_times_for_analyzed_repos) / len(recovery_times_for_analyzed_repos)
        print(f"Mean Time to Recover: {avg_recovery_time:.2f} hours")
    else:
        print(f"Mean Time to Recover: No recovery time data available")
    
    return df_developers, df_repos

def save_cache(data, org):
    cache_file = f"{org}_{CACHE_FILE}"
    with open(cache_file, 'w') as f:
        json.dump(data, f)

def load_cache(org):
    cache_file = f"{org}_{CACHE_FILE}"
    if os.path.exists(cache_file):
        with open(cache_file, 'r') as f:
            return json.load(f)
    return None

def main(org, months, repos_count=20, target_repos=None, use_cache=False, update_cache=False):
    if use_cache and not update_cache:
        data = load_cache(org)
        if data:
            print("Using cached data")
            
            # If target repos specified, filter cached data
            if target_repos:
                data['repos'] = [repo for repo in data['repos'] if repo['name'] in target_repos]
                print(f"Filtered cache to {len(data['repos'])} target repositories")
            
            # Debug: check if there are any PR reviews and comments in the cache
            review_count = 0
            comment_count = 0
            for repo_name in data['pr_reviews']:
                for pr_number in data['pr_reviews'][repo_name]:
                    review_count += len(data['pr_reviews'][repo_name][pr_number] or [])
            
            for repo_name in data['pr_comments']:
                for pr_number in data['pr_comments'][repo_name]:
                    comment_count += len(data['pr_comments'][repo_name][pr_number] or [])
            
            print(f"DEBUG: Found {review_count} reviews and {comment_count} comments in cache")
        else:
            print("Cache not found, fetching new data")
            use_cache = False

    if not use_cache or update_cache:
        # Set the time range for data collection
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30*months)
        since = start_date.isoformat()

        print(f"\nFetching data from GitHub API for organization: {org}")
        data = fetch_data(org, since, target_repos)
        save_cache(data, org)
        print("Data fetched and cached")

    # Always use the specified time range for analysis, even if cached data is older
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30*months)
    since = start_date.isoformat()

    df_developers, df_repos = analyze_data(data, since)
    
    # Save results to CSV files
    df_developers.to_csv(f'{org}_github_developer_metrics.csv', index=False)
    df_repos.to_csv(f'{org}_github_repository_metrics.csv', index=False)
    
    print(f"\nResults saved to {org}_github_developer_metrics.csv and {org}_github_repository_metrics.csv")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="GitHub Metrics Script")
    parser.add_argument("org", help="GitHub organization name")
    parser.add_argument("--months", type=int, default=3, help="Number of months to analyze (default: 3)")
    parser.add_argument("--repos", type=int, default=20, help="Number of top repositories to analyze when no specific repos are targeted (default: 20)")
    parser.add_argument("--target-repos", nargs='+', help="List of specific repositories to analyze (e.g., --target-repos repo-a repo-b)")
    parser.add_argument("--use-cache", action="store_true", help="Use cached data if available")
    parser.add_argument("--update-cache", action="store_true", help="Update the cache with fresh data")
    args = parser.parse_args()

    if not GITHUB_TOKEN:
        print("Error: GITHUB_TOKEN environment variable is not set.")
        print("Set it with: export GITHUB_TOKEN=your_github_token")
        exit(1)

    print(f"Using token: {GITHUB_TOKEN[:4]}...{GITHUB_TOKEN[-4:]}")
    print(f"Organization: {args.org}")
    print(f"Analyzing data for the last {args.months} months")
    
    if args.target_repos:
        print(f"Analyzing specific repositories: {', '.join(args.target_repos)}")
    else:
        print(f"Analyzing top {args.repos} repositories")
        
    main(args.org, args.months, args.repos, args.target_repos, use_cache=args.use_cache, update_cache=args.update_cache)
