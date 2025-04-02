import os
import shutil
import git
import traceback
import stat
import subprocess
import pandas as pd


class LocalRepoProcessor:
    def __init__(self, base_clone_dir="C:/Users/Luka/Development/2024/IRD2/cloned_repo"):
        self.base_clone_dir = base_clone_dir
        self.base_project_path = 'C:/Users/Luka/OneDrive - Univerza v Mariboru/Dokumenti/doktorat/2023-24/IRD2/GHA-scrape'
        if not os.path.exists(self.base_clone_dir):
            os.makedirs(self.base_clone_dir)

    def change_dir_to_default(self ):
        os.chdir(self.base_project_path)
    def change_dir_to_base_clone_dir(self):
        os.chdir(self.base_clone_dir)

    def change_dir_to_cloned_repo_dir(self, repo_name):
        os.chdir(f"{self.base_clone_dir}/{repo_name}")

    #def clone_repo(self, git_url, repo_name, default_branch):
    #    clone_location = os.path.join(self.base_clone_dir, repo_name)
    #    self.prepare_clone_path(clone_location)
    #    print(f"Cloning repository from {git_url}...")
    #    subprocess.run(["git", "clone", "--no-checkout", git_url, clone_location], check=True)
    #    print("Repository cloned.")

    def clone_repo(self, clone_url, repo_name, default_branch):
        try:
            clone_path = os.path.join(self.base_clone_dir, repo_name)
            self.prepare_clone_path(clone_path)
            self.change_dir_to_base_clone_dir()
            # Clone the repository without checking out files
            repo = git.Repo.clone_from(clone_url, clone_path, no_checkout=True)

            # Configure sparse checkout
            repo.git.config('core.sparseCheckout', 'true')
    #
    #        # Write the desired directory to the sparse-checkout file
            sparse_checkout_path = os.path.join(clone_path, '.git', 'info', 'sparse-checkout')
            with open(sparse_checkout_path, 'w') as f:
                f.write('.github/workflows/*\n')
    #
            # Now checkout to the default branch and apply the sparse checkout
            repo.git.checkout(default_branch)

            print(f"Repository cloned at: {clone_path}")  # Debugging line
            print(f"Directory exists after cloning: {os.path.exists(clone_path)}")  # Debugging line
            self.change_dir_to_default()
            return True
        except Exception as e:
            print(f"Error cloning repository: {e}")
            self.change_dir_to_default()
            traceback.print_exc()
            return False

    def get_files_at_commit(self, repo_name, commit_sha):
        try:
            self.change_dir_to_cloned_repo_dir(repo_name)
            command = ['git', 'ls-tree', '-r', '--name-only', f'{commit_sha}:.github/workflows/']
            try:
                file_list = subprocess.check_output(command).strip().decode('utf-8').split('\n')
            except subprocess.CalledProcessError as e:
                print(f"No .github/workflows/ directory at commit {commit_sha}. Returning empty content and file list.")
                self.change_dir_to_default()
                return "", []  # Return empty content and an empty list
            yaml_files_content = ""
            yaml_file_names = []
            for file in file_list:
                if file.endswith('.yml') or file.endswith('.yaml'):
                    command = ['git', 'show', f'{commit_sha}:.github/workflows/{file}']
                    try:
                        file_content = subprocess.check_output(command).decode('utf-8')  # Use 'utf-8' encoding
                    except UnicodeDecodeError:
                        file_content = subprocess.check_output(command).decode(
                            'ISO-8859-1')  # Use 'ISO-8859-1' encoding for files that can't be decoded with 'utf-8'

                    yaml_files_content += file_content
                    yaml_file_names.append(file)
            self.change_dir_to_default()  # Change back to the original working directory
            return yaml_files_content, yaml_file_names
        except Exception as e:
            print(f"Error in get_files_at_commit: {e}")  # Debugging line
            self.change_dir_to_default()  # Change back to the original working directory in case of an error
            return None, None

    def get_files_at_date(self, repo_dir, date):
        try:
            original_dir = os.getcwd()
            os.chdir(repo_dir)
            # Use HEAD@{date} to access the repo state as of the given date
            command = ['git', 'ls-tree', '-r', '--name-only', f'HEAD@{{{date}}}']
            file_list = subprocess.check_output(command).strip().decode('utf-8').split('\n')
            yaml_files_content = ""
            for file in file_list:
                if file.startswith('.github/workflows/') and (file.endswith('.yml') or file.endswith('.yaml')):
                    command = ['git', 'show', f'HEAD@{{{date}}}:{file}']
                    try:
                        file_content = subprocess.check_output(command).decode('utf-8')
                    except UnicodeDecodeError:
                        file_content = subprocess.check_output(command).decode('ISO-8859-1')
                    yaml_files_content += file_content
            os.chdir(original_dir)
            return yaml_files_content
        except Exception as e:
            print(f"Error in get_files_at_date: {e}")
            os.chdir(original_dir)
            return None

    def get_commit_by_date(self, repo_dir, date, default_branch):
        try:
            original_dir = os.getcwd()  # Store the original working directory
            os.chdir(repo_dir)

            # Prepare the command to get the first commit SHA
            first_commit_cmd = ['git', 'rev-list', '--max-parents=0', default_branch]
            first_commit_sha = subprocess.check_output(first_commit_cmd).strip().decode('utf-8')

            if date == "first":
                # If 'date' is the first commit indicator, return the first commit SHA and date
                commit_sha = first_commit_sha
                commit_date_cmd = ['git', 'show', '-s', '--format=%ci', commit_sha]
                commit_date = subprocess.check_output(commit_date_cmd).strip().decode('utf-8')
                commit_date = pd.to_datetime(commit_date).tz_localize(None)
                os.chdir(original_dir)
                return commit_sha, commit_date

            # Prepare the command for the specified date
            command = ['git', 'rev-list', '-n', '1', '--before="' + date.strftime("%Y-%m-%d %H:%M:%S") + '"',
                       default_branch]
            print(f"Running command: {' '.join(command)}")  # Debugging line to show the exact command

            # Execute the command to get the commit SHA
            commit_sha = subprocess.check_output(command).strip().decode('utf-8')

            if not commit_sha:
                print(f"No commit found before {date}. Falling back to the latest commit.")
                # Fallback to the latest commit
                fallback_command = ['git', 'rev-list', '-n', '1', default_branch]
                commit_sha = subprocess.check_output(fallback_command).strip().decode('utf-8')

            print(f"Retrieved commit SHA: {commit_sha}")  # Debugging line to show the retrieved commit SHA

            if commit_sha:
                # Get the date of the selected commit
                commit_date_cmd = ['git', 'show', '-s', '--format=%ci', commit_sha]
                print(f"Running command to get commit date: {' '.join(commit_date_cmd)}")  # Debugging line

                commit_date = subprocess.check_output(commit_date_cmd).strip().decode('utf-8')
                commit_date = pd.to_datetime(commit_date).tz_localize(None)

                print(f"Retrieved commit date: {commit_date}")  # Debugging line to show the retrieved commit date
            else:
                commit_date = None

            os.chdir(original_dir)  # Change back to the original working directory
            return commit_sha, commit_date
        except subprocess.CalledProcessError as e:
            print(f"Git command failed with error: {e}")  # Debugging line for subprocess errors
            os.chdir(original_dir)  # Change back to the original working directory in case of an error
            return None, None
        except Exception as e:
            print(f"Error in get_commit_by_date: {e}")  # Debugging line for other errors
            os.chdir(original_dir)  # Change back to the original working directory in case of an error
            return None, None

    @staticmethod
    def prepare_clone_path(clone_path):
        if os.path.exists(clone_path):
            for root, dirs, files in os.walk(clone_path, topdown=False):
                for name in files:
                    filepath = os.path.join(root, name)
                    os.chmod(filepath, stat.S_IWUSR)
                for name in dirs:
                    dirpath = os.path.join(root, name)
                    os.chmod(dirpath, stat.S_IWUSR)
            shutil.rmtree(clone_path)
        os.makedirs(clone_path, exist_ok=True)
