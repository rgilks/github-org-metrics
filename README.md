# GitHub Organization Metrics

This Python script fetches and analyzes metrics for a specified GitHub organization, providing insights into repository activity and developer contributions.

## Features

- Fetches data for all repositories in a specified GitHub organization
- Analyzes developer activity (commits, lines added/deleted)
- Provides detailed repository metrics (activity, creation date, last update, language, etc.)
- Caches data to reduce API calls and allow for quick re-analysis
- Outputs results to CSV files for further analysis

## Prerequisites

- Python 3.8 or higher
- Git (for cloning the repository)
- GitHub Personal Access Token with appropriate permissions

## Installing Python

If you are on macos install homebrew is it's not already installed
```
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

Install python3.8
```
brew install python@3.8
```

Install pip
```
python3.8 -m pip install --upgrade pip
```   

## Installation and Setup

1. Clone the repository:
   ```
   git clone https://github.com/your-username/github-org-metrics.git
   cd github-org-metrics
   ```

2. Create and activate a virtual environment:
   ```
   python3.8 -m venv myenv
   source myenv/bin/activate
   ```

3. Install the required dependencies:
   ```
   pip3 install -r requirements.txt
   ```

4. Set up your GitHub Personal Access Token:
   - Go to GitHub Settings > Developer Settings > Personal Access Tokens > Fine-grained tokens
   - Create a new token with the following permissions:
     - Organization permissions:
       * Read access to members and organization administration
     - Repository permissions:
       * Read access to code and metadata

5. Set your token as an environment variable:
   ```
   export GITHUB_TOKEN=your_fine_grained_token_here
   ```

## Usage

Ensure your virtual environment is activated, then run the script using the following command:

```
python3.8 github_metrics.py <organization_name> [--use-cache] [--update-cache]
```

Arguments:
- `<organization_name>`: The name of the GitHub organization you want to analyze (required)
- `--use-cache`: Use cached data if available (optional)
- `--update-cache`: Update the cache with fresh data (optional)

Examples:
- To fetch new data for an organization:
  ```
  python3.8 github_metrics.py MyOrgName
  ```
- To use cached data (if available):
  ```
  python3.8 github_metrics.py MyOrgName --use-cache
  ```
- To update the cache with fresh data:
  ```
  python3.8 github_metrics.py MyOrgName --update-cache
  ```

## Output

The script generates two CSV files:

1. `<org_name>_github_developer_metrics.csv`: Contains metrics for each developer, including:
   - Number of commits
   - Lines added and deleted
   - Top 8 repositories contributed to (sorted by number of commits)

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

- The script currently analyzes data from the last 6 months. To change this, modify the `timedelta(days=180)` in the `main()` function.

## Limitations

- The script may take a while to run for large organizations with many repositories.
- It's subject to GitHub API rate limits.
- Some data may not be available depending on the permissions of your Personal Access Token.

## Troubleshooting

If you encounter issues:
1. Ensure your GitHub token has the necessary permissions.
2. Check that you're not hitting GitHub's API rate limits.
3. For large organizations, consider running the script in parts or reducing the time range analyzed.
4. If you're having dependency issues, try updating your dependencies:
   ```
   pip3 install --upgrade -r requirements.txt
   ```

## License

This project is open-source and available under the MIT License.
