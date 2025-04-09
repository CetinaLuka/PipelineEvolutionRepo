import subprocess
import os
import pandas as pd
import shutil
import stat

from Repo import Repo


class CommitsExtractor:

    @staticmethod
    def get_commits_for_repo(repo_obj, clone_path):
        print(f"Cloning {repo_obj.clone_url} into {clone_path}")
        CommitsExtractor.clone_repo(repo_obj.clone_url, clone_path)
        print(f"Extracting commit data from {clone_path}")
        commit_data = CommitsExtractor.extract_commit_data(clone_path)
        rows = CommitsExtractor.format_commits(repo_obj, commit_data)
        return rows

    @staticmethod
    def get_last_processed_repo(csv_path="data/repo_commits.csv"):
        """Find the last repository processed."""
        try:
            df_commits = pd.read_csv(csv_path)
            if df_commits.empty:
                return None
            df_commits['full_name'] = df_commits['repo_owner'] + '/' + df_commits['repo_name']
            last_repo_full_name = df_commits.iloc[-1]['full_name']
            return last_repo_full_name
        except FileNotFoundError:
            return None
    @staticmethod
    def get_commits_for_all_repos_in_csv(repos_csv_file_path="data/all_repos_has_pipeline_check.csv"):
        # get commits for all repos with pipelines
        repos = Repo.create_repo_objects_from_csv(repos_csv_file_path)
        # filter repos so only the ones that have pipelines are processed for commits
        repos = [repo for repo in repos if repo.has_pipeline]
        print(f"Processing {len(repos)} repositories with pipelines...")
        repo_commits = []
        last_processed_repo = CommitsExtractor.get_last_processed_repo()
        print("last_processed_repo: ", last_processed_repo)

        # Assume we have not found the start if there is a last_processed_repo
        found_start = last_processed_repo is None

        for repo in repos:
            # Skip processing until the last processed repo is found
            if not found_start:
                if repo.full_name == last_processed_repo:
                    found_start = True  # Found the last processed repo, so start processing from the next one
                continue  # Skip this repo if it's the last processed one or if we haven't found the last processed one yet

            # From this point on, found_start is True, so we process current and subsequent repos
            print(f"Processing {repo.full_name}")
            commits = CommitsExtractor.get_commits_for_repo(repo, "C:/Users/Luka/Development/2024/IRD2/cloned_repo")
            repo_commits.extend(commits)
            CommitsExtractor.save_commits_to_csv(commits, "data/repo_commits.csv")
    @staticmethod
    def save_commits_to_csv(commits, csv_path="data/repo_commits.csv"):
        """Save a list of commit dictionaries to a CSV file."""
        df_commits = pd.DataFrame(commits)
        # Check if the file exists to decide on writing headers
        header = not pd.io.common.file_exists(csv_path)
        df_commits.to_csv(csv_path, mode='a', header=header, index=False)

    #@staticmethod
    #def get_last_processed_repo(csv_path="data/repo_commits.csv"):
    #    """Get the full name of the last processed repository from the commits CSV file."""
    #    try:
    #        df = pd.read_csv(csv_path)
    #        if not df.empty:
    #            return df.iloc[-1]['full_name']
    #    except FileNotFoundError:
    #        pass
    #    return None





    @staticmethod
    def prepare_clone_path(clone_path):
        print(f"Preparing clone path at {clone_path}")
        if os.path.exists(clone_path):
            print("Path exists. Cleaning up...")
            for root, dirs, files in os.walk(clone_path, topdown=False):
                for name in files:
                    filepath = os.path.join(root, name)
                    os.chmod(filepath, stat.S_IWUSR)
                for name in dirs:
                    dirpath = os.path.join(root, name)
                    os.chmod(dirpath, stat.S_IWUSR)
            shutil.rmtree(clone_path)
        os.makedirs(clone_path, exist_ok=True)
        print("Clone path prepared.")

    @staticmethod
    def clone_repo(git_url, clone_path):
        CommitsExtractor.prepare_clone_path(clone_path)
        print(f"Cloning repository from {git_url}...")
        subprocess.run(["git", "clone", "--no-checkout", git_url, clone_path], check=True)
        print("Repository cloned.")

    @staticmethod
    def extract_commit_data(repo_path):
        print("Starting commit parsing...")
        cmd = ["git", "-C", repo_path, "log", "--pretty=format:%H %ai %s", "--numstat"]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, encoding='utf-8')
        print("Commit data extraction in progress...")
        print(result.stdout)
        commit_data = []
        current_commit = None  # Start with no current commit

        for line in result.stdout.splitlines():
            if line.strip():
                parts = line.split(maxsplit=3)
                # Check if this line starts with a commit hash
                if len(parts[0]) == 40 and all(c.isalnum() for c in parts[0]):
                    if current_commit:  # If there's an existing commit being processed, save it
                        commit_data.append(current_commit)
                    # Start a new commit entry
                    current_commit = {
                        'hash': parts[0],
                        'date': parts[1] + " " + parts[2] if len(parts) > 2 else "Unknown Date",
                        'message': parts[3] if len(parts) > 3 else "",
                        'additions': 0,
                        'deletions': 0,
                        'changes_pipeline': False,
                        'diff': ''
                    }
                elif current_commit:  # Process numstat lines only if there's an active commit
                    if len(parts) >= 3:
                        additions, deletions, filename = parts[0], parts[1], ' '.join(parts[2:])
                        current_commit['additions'] += int(additions) if additions.isdigit() else 0
                        current_commit['deletions'] += int(deletions) if deletions.isdigit() else 0
                        if ".github/workflows" in filename and filename.endswith(".yml"):
                            current_commit['changes_pipeline'] = True

        # Add the last commit if it exists
        if current_commit:
            commit_data.append(current_commit)
        print("Commit data extraction completed.")
        return commit_data

    @staticmethod
    def format_commits(repo_obj, commits):
        print(f"Formatting commits for {repo_obj.name}...")
        rows = []
        for commit in commits:
            rows.append({
                'repo_name': repo_obj.name,
                'repo_full_name': repo_obj.full_name,
                'repo_owner': repo_obj.owner,
                'repo_created': repo_obj.createdAt,
                'repo_updated': repo_obj.updatedAt,
                'repo_language': repo_obj.language,
                'repo_duration': repo_obj.duration,
                'repo_num_contributors': repo_obj.number_of_contributors,
                'commit_hash': commit['hash'],
                'commit_date': commit['date'],
                'commit_message': commit['message'],
                'total_additions': commit['additions'],
                'total_deletions': commit['deletions'],
                'changes_pipeline': commit['changes_pipeline']
            })
        print(f"Finished formatting commits for {repo_obj.name}.")
        return rows

    @staticmethod
    def clone_and_check_github_actions(repo_list, clone_path):
        updated_repos = []  # Initialize a list to hold the updated repository objects
        for index, repo_obj in repo_list.iterrows():
            # Prepare the clone path
            CommitsExtractor.prepare_clone_path(clone_path)

            # Initialize the Git repository
            subprocess.run(["git", "init", clone_path], check=True)

            # Add the remote repository
            subprocess.run(["git", "-C", clone_path, "remote", "add", "origin", repo_obj['clone_url']], check=True)

            # Fetch the specified branch with a shallow depth to minimize data transfer
            subprocess.run(["git", "-C", clone_path, "fetch", "--depth=1", "origin", repo_obj['default_branch']], check=True)

            # Enable sparse checkout
            subprocess.run(["git", "-C", clone_path, "config", "core.sparseCheckout", "true"], check=True)

            # Write the sparse-checkout file to specify the paths you want
            with open(os.path.join(clone_path, ".git/info/sparse-checkout"), "w") as f:
                f.write(".github/workflows\n")

            # Checkout the sparse paths from the fetched content
            subprocess.run(["git", "-C", clone_path, "checkout", "FETCH_HEAD"], check=True)

            # Check if any .yml files exist
            workflows_path = os.path.join(clone_path, '.github', 'workflows')
            updated_repo = repo_obj
            updated_repo['has_pipeline'] = False
            if os.path.exists(workflows_path) and os.path.isdir(workflows_path):
                for filename in os.listdir(workflows_path):
                    if filename.endswith('.yml') or filename.endswith('.yaml'):
                        updated_repo['has_pipeline'] = True
                        break
            print(updated_repo)
            updated_repos.append(updated_repo)

        return updated_repos
