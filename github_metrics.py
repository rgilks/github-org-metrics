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

def get_org_repos(org, since):
    repos = []
    page = 1
    while True:
        url = f"{GITHUB_API_URL}/orgs/{org}/repos?page={page}&per_page=100&type=all&sort=pushed&direction=desc"
        print(f"Fetching: {url}")
        page_repos = make_request(url)
        if not page_repos:
            break
        repos.extend([repo for repo in page_repos if repo['pushed_at'] >= since])
        print(f"Retrieved {len(repos)} repositories updated since {since}")
        if len(page_repos) < 100 or len(repos) >= 20:
            break
        page += 1
    return repos[:20]  # Return only the top 20 repos

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

def fetch_data(org, since):
    data = {
        'repos': get_org_repos(org, since),
        'commits': {},
        'commit_stats': {},
        'branches': {},
        'contributors': {},
        'pull_requests': {},
        'pr_reviews': {},
        'pr_comments': {}
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
        for pr in data['pull_requests'][repo_name]:
            pr_number = pr['number']
            data['pr_reviews'][repo_name][pr_number] = get_pull_request_reviews(org, repo_name, pr_number)
            data['pr_comments'][repo_name][pr_number] = get_pull_request_comments(org, repo_name, pr_number)
    
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
    pr_merge_times = []
    branch_lifetimes = []
    
    # Debug counters
    total_prs_processed = 0
    total_reviews_found = 0
    total_comments_found = 0
    
    # Fix: Pre-count all PR reviews and comments by user
    for repo_name in data['pr_reviews']:
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
    
    print(f"DEBUG: Pre-counted {total_reviews_found} reviews ({len(pr_reviews)} reviewers)")
    print(f"DEBUG: Pre-counted {total_comments_found} comments ({len(pr_comments)} commenters)")
    
    for repo in data['repos']:
        repo_name = repo['name']
        repo_details.append({
            'name': repo_name,
            'created_at': datetime.strptime(repo['created_at'], "%Y-%m-%dT%H:%M:%SZ").strftime("%B %d, %Y"),
            'updated_at': datetime.strptime(repo['updated_at'], "%Y-%m-%dT%H:%M:%SZ").strftime("%B %d, %Y"),
            'language': repo['language'] or 'N/A',
            'branch_count': len(data['branches'][repo_name]),
            'contributor_count': len(data['contributors'][repo_name]),
        })
        
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
                        pr_merge_times.append((merged_at - created_at).total_seconds() / 3600)  # in hours
                        
                        # Calculate branch lifetime
                        branch_created_at = datetime.strptime(pr['head']['repo']['created_at'], "%Y-%m-%dT%H:%M:%SZ")
                        branch_lifetimes.append((merged_at - branch_created_at).total_seconds() / 3600)  # in hours
                
                total_prs_processed += 1

    print(f"DEBUG: Processed {total_prs_processed} PRs")
    print(f"DEBUG: Found {total_reviews_found} reviews during analysis")
    print(f"DEBUG: Found {total_comments_found} comments during analysis")
    print(f"DEBUG: PR Reviews counter has {sum(pr_reviews.values())} entries")
    print(f"DEBUG: PR Comments counter has {sum(pr_comments.values())} entries")

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

    df_repos = pd.DataFrame(repo_details)
    df_repos['Activity'] = df_repos['name'].map(repo_activity)
    df_repos = df_repos[['name', 'Activity', 'created_at', 'updated_at', 'language', 'branch_count', 'contributor_count']]
    df_repos = df_repos.sort_values('Activity', ascending=False)

    # Calculate averages
    avg_pr_merge_time = sum(pr_merge_times) / len(pr_merge_times) if pr_merge_times else 0
    avg_branch_lifetime = sum(branch_lifetimes) / len(branch_lifetimes) if branch_lifetimes else 0

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
        'created_at': lambda x: f'{x:>20}',
        'updated_at': lambda x: f'{x:>20}',
        'language': lambda x: f'{x:<10}',
        'branch_count': lambda x: f'{x:>12}',
        'contributor_count': lambda x: f'{x:>18}'
    }

    print("\nFinal Results:")
    print(f"Total Repositories Processed: {len(data['repos'])}")
    print(f"\nAverage PR Merge Time: {avg_pr_merge_time:.2f} hours")
    print(f"Average Branch Lifetime: {avg_branch_lifetime:.2f} hours")
    print("\nDeveloper Activity:")
    print(df_developers.to_string(index=False, formatters=developer_formatters, justify='left'))
    print("\nRepository Details:")
    print(df_repos.to_string(index=False, formatters=repo_formatters, justify='left'))

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

def main(org, months, repos, use_cache=False, update_cache=False):
    if use_cache and not update_cache:
        data = load_cache(org)
        if data:
            print("Using cached data")
            
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
        data = fetch_data(org, since)
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
    parser.add_argument("--repos", type=int, default=20, help="Number of top repositories to analyze (default: 20)")
    parser.add_argument("--use-cache", action="store_true", help="Use cached data if available")
    parser.add_argument("--update-cache", action="store_true", help="Update the cache with fresh data")
    args = parser.parse_args()

    if not GITHUB_TOKEN:
        print("Error: GITHUB_TOKEN environment variable is not set.")
        exit(1)

    print(f"Using token: {GITHUB_TOKEN[:4]}...{GITHUB_TOKEN[-4:]}")
    print(f"Organization: {args.org}")
    print(f"Analyzing data for the last {args.months} months")
    print(f"Analyzing top {args.repos} repositories")
    main(args.org, args.months, args.repos, use_cache=args.use_cache, update_cache=args.update_cache)
