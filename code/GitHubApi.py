from datetime import datetime, timedelta

import pandas as pd
import requests
import Repo
from dotenv import load_dotenv
import os
import yaml
import time


class GitHubApi:
    def __init__(self):
        load_dotenv()
        token = os.getenv("GITHUB_TOKEN")
        self.api = 'https://api.github.com'
        self.headers = {
            'Authorization': 'Bearer ' + token
        }

    def get_java_repo_list_by_stars(self, csv_path="data/all_repos.csv", max_pages=None, created_at=None):
        try:
            df_existing = pd.read_csv(csv_path)
            already_fetched_pages = len(df_existing) // 100
            start_page = already_fetched_pages + 1
            print(f"Resuming from page {start_page}. Already fetched {already_fetched_pages} pages.")
        except FileNotFoundError:
            df_existing = pd.DataFrame()
            already_fetched_pages = 0
            start_page = 1

        # Calculate the total number of pages to fetch based on max_pages and what's already been fetched
        pages_to_fetch = max_pages - already_fetched_pages if max_pages is not None else None

        # If pages_to_fetch is 0 or negative, no need to fetch more pages
        if pages_to_fetch is not None and pages_to_fetch <= 0:
            print("No additional pages need to be fetched based on the max_pages parameter.")
            return df_existing
        year_filter = f' created:>{created_at}' if created_at is not None else ''
        params = {
            'q': 'language:java' + year_filter,
            'sort': 'stars',
            'order': 'desc',
            'per_page': 100,
            'page': start_page
        }

        pages_fetched = 0  # Keep track of the number of pages fetched in this session

        while True:
            if pages_to_fetch is not None and pages_fetched >= pages_to_fetch:
                break

            response = requests.get(f'{self.api}/search/repositories', headers=self.headers, params=params)
            if response.status_code == 200:
                repositories = response.json()['items']
                if not repositories:
                    break  # No more repositories to fetch

                repos = []
                for item in repositories:
                    repo = {
                        'owner': item['owner']['login'],
                        'name': item['name'],
                        'full_name': item['full_name'],
                        'repo_url': item['html_url'],
                        'api_url': item['url'],
                        'default_branch': item.get('default_branch', ''),
                        'description': item['description'],
                        'created_at': item['created_at'],
                        'updated_at': item['updated_at'],
                        'duration': (datetime.strptime(item['updated_at'], '%Y-%m-%dT%H:%M:%SZ') - datetime.strptime(
                            item['created_at'], '%Y-%m-%dT%H:%M:%SZ')).days,
                        'size_kb': item['size'],
                        'stars': item['stargazers_count'],
                        'language': item['language'],
                        'clone_url': item['clone_url'],
                        'topics': item['topics'] if 'topics' in item else ''
                    }
                    repos.append(repo)
                df_repos = pd.DataFrame(repos)
                df_repos.to_csv(csv_path, mode='a', index=False, header=df_existing.empty)
                print(f"Page {params['page']} fetched and saved.")

                df_existing = pd.concat([df_existing, df_repos], ignore_index=True)
                params['page'] += 1
                pages_fetched += 1
            elif response.status_code == 403:
                print("Rate limit exceeded. Try again later.")
                break
            else:
                print(f"Failed to fetch data: {response.status_code}")
                print(response.headers)
                print(response.request.url)
                break

        return df_existing

    def check_repos_for_github_actions(self, repo_list_csv_path="data/all_repos.csv",
                                       new_csv_path="data/all_repos_has_pipeline_check_old.csv"):
        try:
            # Attempt to load the progress file
            df_progress = pd.read_csv(new_csv_path)
            processed_repos = set(df_progress['full_name'])
        except FileNotFoundError:
            df_progress = pd.DataFrame(columns=['owner', 'name', 'full_name', 'has_pipeline'])
            processed_repos = set()

        df_repos = pd.read_csv(repo_list_csv_path)

        # Only process repos that haven't been checked yet
        for index, repo in df_repos.iterrows():
            full_name = repo['full_name']
            print(f"Processing {full_name}")
            if full_name in processed_repos:
                continue  # Skip repos that have already been processed

            owner = repo['owner']
            repo_name = repo['name']
            workflows_url = f"https://api.github.com/repos/{owner}/{repo_name}/contents/.github/workflows"

            has_pipeline = False
            response = requests.get(workflows_url, headers=self.headers)
            yaml_files_content = ""  # will contain the content all yaml files
            workflows = []
            number_of_workflows = 0
            if response.status_code == 200:
                for file in response.json():
                    if file['name'].endswith('.yml') or file['name'].endswith('.yaml'):
                        has_pipeline = True
                        number_of_workflows += 1
                        workflows.append(file['name'])
                        yaml_download_url = file['download_url']
                        # download the content of the yaml file and save it to yaml_files_content add a newline after every file
                        yaml_files_content += requests.get(yaml_download_url, headers=self.headers).text + "\n---\n"
            # Update the row in the DataFrame
            new_row = {**repo,
                       'has_pipeline': has_pipeline,
                       'yaml_files_content': yaml_files_content,
                       }
            new_row_df = pd.DataFrame([new_row])  # Convert the single row to a DataFrame
            df_progress = pd.concat([df_progress, new_row_df], ignore_index=True)

            # Save progress incrementally
            df_progress.to_csv(new_csv_path, index=False)

            if response.status_code not in [200, 404]:
                print(f"Failed to fetch data for {repo_name}: {response.status_code}")
                break  # Stop if there's an error other than not found

        return df_progress

    def get_repo(self, repo_full_name):
        response = requests.get(f'{self.api}/repos/{repo_full_name}', headers=self.headers)
        repo = Repo.Repo(response.json())
        repo.number_of_contributors = self.get_number_of_contributors(repo_full_name)
        # repo.commits = self.get_commits(repo_full_name)
        return repo

    def get_number_of_contributors(self, repo_full_name):
        response = requests.get(f'{self.api}/repos/{repo_full_name}/contributors', headers=self.headers)
        return len(response.json())

    def fetch_all_workflow_runs(self,owner, repo, branch):
        url = f"https://api.github.com/repos/{owner}/{repo}/actions/runs"
        all_runs = []
        params = {
            "per_page": 100,  # Max allowed
            "branch": branch  # Fetch only runs from the default branch
        }

        while url:
            print(f"📡 Fetching workflow runs for {owner}/{repo} on branch {branch}...")
            response = requests.get(url, headers=self.headers, params=params)

            if response.status_code == 403 and "X-RateLimit-Remaining" in response.headers:
                reset_time = int(response.headers.get("X-RateLimit-Reset", time.time()))
                sleep_time = max(1, reset_time - int(time.time()))
                print(f"⏳ Rate limit reached! Sleeping for {sleep_time} seconds...")
                time.sleep(sleep_time)
                continue

            if response.status_code != 200:
                print(f" Failed to fetch {owner}/{repo}, Status: {response.status_code}")
                break

            data = response.json()
            runs = data.get("workflow_runs", [])

            if not runs:
                print(f" No workflow runs found for {owner}/{repo}")
                break

            for run in runs:
                run_data = {
                    "repo": f"{owner}/{repo}",
                    "branch": branch,
                    "run_id": run["id"],
                    "status": run["status"],
                    "conclusion": run.get("conclusion", "N/A"),
                    "created_at": run["created_at"],
                    "updated_at": run["updated_at"],
                    "duration": (
                            pd.to_datetime(run["updated_at"]) - pd.to_datetime(run["created_at"])
                    ).total_seconds() if run.get("updated_at") else None
                }
                all_runs.append(run_data)

            link_header = response.headers.get("Link", "")
            next_url = None
            for part in link_header.split(","):
                if 'rel="next"' in part:
                    next_url = part.split(";")[0].strip(" <>")
                    break
            url = next_url

            remaining_requests = int(response.headers.get("X-RateLimit-Remaining", 1))
            print(f"Fetched {len(runs)} runs. API Calls Remaining: {remaining_requests}")
            if remaining_requests == 0:
                print("Rate limit reached! Waiting 60 seconds...")
                time.sleep(60)

        return all_runs