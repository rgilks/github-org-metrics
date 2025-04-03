# GitHub Organization Metrics

This Python script fetches and analyzes metrics for a specified GitHub organization, providing insights into repository activity and developer contributions. It focuses on the top repositories that were changed within a specified time frame.

## Features

- Fetches data for the top repositories in a specified GitHub organization
- Analyzes developer activity (commits, lines added/deleted)
- Provides detailed repository metrics (activity, creation date, last update, language, etc.)
- Allows customization of the number of months to analyze and the number of top repositories to consider
- Caches data to reduce API calls and allow for quick re-analysis
- Outputs results to CSV files for further analysis

## Prerequisites

- Python 3.8 or higher
- Git (for cloning the repository)
- GitHub Personal Access Token with appropriate permissions

## Installing Python

If you are on macos install homebrew if it's not already installed

```
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

Install python

```
brew install python
```

If you install python with homebrew then there's no need to install pip separately.
However if you have a non-homebrew python installation then install pip with:
```
python3 -m pip install --upgrade pip
```

## Installation and Setup

1. Clone the repository:

   ```
   git clone https://github.com/your-username/github-org-metrics.git
   cd github-org-metrics
   ```

2. Create and activate a virtual environment:

   ```
   python3 -m venv myenv
   source myenv/bin/activate
   ```

3. Install the required dependencies:

   ```
   pip install -r requirements.txt
   ```

4. Set up your GitHub Personal Access Token:

   - Go to GitHub Settings > Developer Settings > Personal Access Tokens > Fine-grained tokens
   - Create a new token with the following permissions:
     - Repository permissions:
       - Actions: Read-only
       - Contents: Read-only
       - Deployments: Read-only
       - Issues: Read-only
       - Metadata: Read-only
       - Pull Requests: Read-only
     - Organization permissions:
       - Administration: Read-only
       - Members: Read-only

5. Set your token as an environment variable:
   ```
   export GITHUB_TOKEN=your_fine_grained_token_here
   ```

## Usage

Ensure your virtual environment is activated, then run the script using the following command:

```
python3 github_metrics.py <organization_name> [--months MONTHS] [--repos REPOS] [--use-cache] [--update-cache] [--target-repos REPOS]
```

Arguments:

- `<organization_name>`: The name of the GitHub organization you want to analyze (required)
- `--months MONTHS`: Number of months to analyze (default: 3)
- `--repos REPOS`: Number of top repositories to analyze (default: 20)
- `--use-cache`: Use cached data if available (optional)
- `--update-cache`: Update the cache with fresh data (optional)
- `--target-repos REPOS`: Comma-separated list of repositories to analyze (optional)

Examples:

- To fetch new data for an organization's top 20 repos in the last 3 months:
  ```
  python3 github_metrics.py MyOrgName
  ```
- To analyze the top 10 repos from the last 6 months:
  ```
  python3 github_metrics.py MyOrgName --months 6 --repos 10
  ```
- To use cached data (if available):
  ```
  python3 github_metrics.py MyOrgName --use-cache
  ```
- To update the cache with fresh data:
  ```
  python3 github_metrics.py MyOrgName --update-cache
  ```
- To analyze specific repositories:
  ```
  python3 github_metrics.py MyOrgName --target-repos repo-a repo-b
  ```

## Output

The script generates two CSV files:

1. `<org_name>_github_developer_metrics.csv`: Contains metrics for each developer, including:

   - Number of commits
   - Lines added and deleted
   - PRs opened, reviewed, and commented on
   - Top repositories contributed to

2. `<org_name>_github_repository_metrics.csv`: Contains metrics for each repository, including:
   - Repository name
   - Activity level (number of commits)
   - Creation and last update dates
   - Primary programming language
   - Number of branches
   - Number of contributors

The script also prints a formatted version of these results to the console.

## Caching

The script uses a JSON file (`<org_name>_github_data_cache.json`) to store raw data. This allows for:

- Quick re-running of analyses without making API calls
- Experimentation with different analysis methods on the same dataset
- Maintenance of a historical record of your GitHub data

## Customization

- You can adjust the number of months to analyze and the number of top repositories to consider using the `--months` and `--repos` arguments.
- The script focuses on repositories that have been pushed to within the specified time frame.

## Limitations

- The script may take a while to run for large organizations with many active repositories.
- It's subject to GitHub API rate limits.
- Some data may not be available depending on the permissions of your Personal Access Token.

## Troubleshooting

If you encounter issues:

1. Ensure your GitHub token has the necessary permissions.
2. Check that you're not hitting GitHub's API rate limits.
3. For large organizations, consider reducing the number of repositories or the time range analyzed.
4. If you're having dependency issues, try updating your dependencies:
   ```
   pip install --upgrade -r requirements.txt
   ```

## License

This project is open-source and available under the MIT License.
