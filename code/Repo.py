import datetime

import pandas as pd


class Repo:
    def __init__(self, response):
        self.owner = response["owner"]["login"]
        self.name = response["name"]
        self.full_name = response["full_name"]
        self.repo_url = response["html_url"]
        self.api_url = response["url"]
        self.default_branch = response["default_branch"]
        self.description = response["description"]
        self.createdAt = response["created_at"]
        self.updatedAt = response["updated_at"]
        self.duration = datetime.datetime.strptime(self.updatedAt, '%Y-%m-%dT%H:%M:%SZ') - datetime.datetime.strptime(self.createdAt, '%Y-%m-%dT%H:%M:%SZ')
        self.size = response["size"] # in KB
        self.stars = response["stargazers_count"]
        self.language = response["language"]
        self.clone_url = response["clone_url"]
        self.has_pipeline = response["has_pipeline"]

        #kasneje se vnesejo vrednosti
        self.number_of_contributors = None
        self.commits = []

    @staticmethod
    def create_repo_objects_from_csv(csv_path):
        df_repos = pd.read_csv(csv_path)
        df_pipeline_repos = df_repos[df_repos['has_pipeline'] == True]
        repo_objects = []

        for index, row in df_pipeline_repos.iterrows():
            # Convert row to dictionary, with keys matching the Repo class's expected input
            repo_data = {
                "owner": {"login": row["owner"]},
                "name": row["name"],
                "full_name": row["full_name"],
                "html_url": row["repo_url"],
                "url": row["api_url"],
                "default_branch": row["default_branch"],
                "description": row["description"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "size": row["size_kb"],
                "stargazers_count": row["stars"],
                "language": row["language"],
                "clone_url": row["clone_url"],
                "has_pipeline": row["has_pipeline"]
            }

            # Create Repo object
            repo_obj = Repo(repo_data)
            # Add the Repo object to the list
            repo_objects.append(repo_obj)

        return repo_objects

    def get_dict(self):
        return {
            "owner": self.owner,
            "name": self.name,
            "repo_url": self.repo_url,
            "api_url": self.api_url,
            "description": self.description,
            "createdAt": self.createdAt,
            "updatedAt": self.updatedAt,
            "duration": self.duration,
            "size": self.size,
            "stars": self.stars,
            "language": self.language,
            "number_of_contributors": self.number_of_contributors,
            "clone_url": self.clone_url
        }

    def __str__(self):
        return f'{self.owner}/{self.name} - {self.repo_url}\n' \
               f'{self.description}\n' \
               f'Created: {self.createdAt}, Updated: {self.updatedAt}\n' \
               f'Size: {self.size} KB, Stars: {self.stars}, Language: {self.language}\n' \
               f'Number of contributors: {self.number_of_contributors}\n' \
               f'API URL: {self.api_url}, Duration: {self.duration}\n' \
                f'Commits: {self.commits}'


