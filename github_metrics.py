import requests
import pandas as pd
from datetime import datetime, timedelta
import os
from collections import defaultdict
import time
import json
import argparse
import base64

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
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 403 and 'X-RateLimit-Remaining' in response.headers and int(response.headers['X-RateLimit-Remaining']) == 0:
            reset_time = int(response.headers['X-RateLimit-Reset'])
            sleep_time = reset_time - time.time() + 1
            print(f"Rate limit exceeded. Sleeping for {sleep_time} seconds.")
            time.sleep(sleep_time)
        else:
            print(f"Error fetching {url}: {response.status_code}")
            print(f"Response content: {response.text}")
            return None

def get_org_repos(org):
    repos = []
    page = 1
    while True:
        url = f"{GITHUB_API_URL}/orgs/{org}/repos?page={page}&per_page=100&type=all"
        print(f"Fetching: {url}")
        page_repos = make_request(url)
        if not page_repos:
            break
        repos.extend(page_repos)
        print(f"Retrieved {len(page_repos)} repositories on page {page}")
        if len(page_repos) < 100:
            break
        page += 1
    print(f"Total repositories found: {len(repos)}")
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

def get_releases(org, repo):
    url = f"{GITHUB_API_URL}/repos/{org}/{repo}/releases"
    return make_request(url)

def get_readme(org, repo):
    url = f"{GITHUB_API_URL}/repos/{org}/{repo}/readme"
    readme_data = make_request(url)
    if readme_data and 'content' in readme_data:
        return base64.b64decode(readme_data['content']).decode('utf-8')
    return None

def fetch_data(org, since):
    data = {
        'repos': get_org_repos(org),
        'commits': {},
        'commit_stats': {},
        'branches': {},
        'contributors': {},
        'releases': {},
        'readme': {}
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
        data['releases'][repo_name] = get_releases(org, repo_name)
        data['readme'][repo_name] = get_readme(org, repo_name)
    
    return data

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

def analyze_data(data, since):
    commit_counts = defaultdict(int)
    lines_added = defaultdict(int)
    lines_deleted = defaultdict(int)
    repos_worked_on = defaultdict(set)
    repo_activity = defaultdict(int)
    repo_details = []
    
    for repo in data['repos']:
        repo_name = repo['name']
        repo_details.append({
            'name': repo_name,
            'private': repo['private'],
            'created_at': repo['created_at'],
            'updated_at': repo['updated_at'],
            'language': repo['language'],
            'stars': repo['stargazers_count'],
            'forks': repo['forks_count'],
            'size': repo['size'],
            'branch_count': len(data['branches'][repo_name]),
            'contributor_count': len(data['contributors'][repo_name]),
            'release_count': len(data['releases'][repo_name]),
            'has_readme': data['readme'][repo_name] is not None,
            'readme_size': len(data['readme'][repo_name]) if data['readme'][repo_name] else 0
        })
        
        for commit in data['commits'][repo_name]:
            if commit['commit']['author']['date'] >= since:
                if commit['author'] and 'login' in commit['author']:
                    author = commit['author']['login']
                    commit_counts[author] += 1
                    repos_worked_on[author].add(repo_name)
                    repo_activity[repo_name] += 1
                    
                    stats = data['commit_stats'][repo_name].get(commit['sha'])
                    if stats:
                        lines_added[author] += stats['additions']
                        lines_deleted[author] += stats['deletions']

    df_developers = pd.DataFrame({
        'Developer': list(commit_counts.keys()),
        'Commits': list(commit_counts.values()),
        'Lines Added': [lines_added[dev] for dev in commit_counts.keys()],
        'Lines Deleted': [lines_deleted[dev] for dev in commit_counts.keys()],
        'Repositories': [', '.join(repos_worked_on[dev]) for dev in commit_counts.keys()]
    })

    df_developers = df_developers.sort_values('Commits', ascending=False)

    df_repos = pd.DataFrame(repo_details)
    df_repos['Activity'] = df_repos['name'].map(repo_activity)
    df_repos = df_repos.sort_values('Activity', ascending=False)

    print("\nFinal Results:")
    print(f"Total Repositories Processed: {len(data['repos'])}")
    print("\nDeveloper Activity:")
    print(df_developers)
    print("\nRepository Details:")
    print(df_repos)

    return df_developers, df_repos

def main(org, use_cache=False, update_cache=False):
    if use_cache and not update_cache:
        data = load_cache(org)
        if data:
            print("Using cached data")
        else:
            print("Cache not found, fetching new data")
            use_cache = False

    if not use_cache or update_cache:
        # Set the time range for data collection (last 6 months)
        end_date = datetime.now()
        start_date = end_date - timedelta(days=180)
        since = start_date.isoformat()

        print(f"\nFetching data from GitHub API for organization: {org}")
        data = fetch_data(org, since)
        save_cache(data, org)
        print("Data fetched and cached")

    # Always use the last 6 months for analysis, even if cached data is older
    end_date = datetime.now()
    start_date = end_date - timedelta(days=180)
    since = start_date.isoformat()

    df_developers, df_repos = analyze_data(data, since)
    
    # Save results to CSV files
    df_developers.to_csv(f'{org}_github_developer_metrics.csv', index=False)
    df_repos.to_csv(f'{org}_github_repository_metrics.csv', index=False)
    
    print(f"\nResults saved to {org}_github_developer_metrics.csv and {org}_github_repository_metrics.csv")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="GitHub Metrics Script")
    parser.add_argument("org", help="GitHub organization name")
    parser.add_argument("--use-cache", action="store_true", help="Use cached data if available")
    parser.add_argument("--update-cache", action="store_true", help="Update the cache with fresh data")
    args = parser.parse_args()

    if not GITHUB_TOKEN:
        print("Error: GITHUB_TOKEN environment variable is not set.")
        exit(1)

    print(f"Using token: {GITHUB_TOKEN[:4]}...{GITHUB_TOKEN[-4:]}")
    print(f"Organization: {args.org}")
    main(args.org, use_cache=args.use_cache, update_cache=args.update_cache)

