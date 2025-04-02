import yaml
import re

class MetricsCalculator:
    def __init__(self, yaml_string):
        self.yaml_string = yaml_string
        self.yaml_files = yaml_string.split('---')
        self.parsed_yaml = []
        for file in self.yaml_files:
            try:
                parsed_file = yaml.safe_load(file)
                if parsed_file and isinstance(parsed_file, dict):
                    self.parsed_yaml.append(parsed_file)
            except yaml.YAMLError:
                pass

    # LOC
    def count_lines_of_code(self):
        return sum(len([line for line in file.split('\n') if line.strip()]) for file in self.yaml_files)

    def count_comments(self):
        return sum(len(re.findall(r'#.*', file)) for file in self.yaml_files)

    def count_steps(self):
        return sum(
            len(job.get('steps', [])) for yaml_content in self.parsed_yaml if yaml_content
            for job in yaml_content.get('jobs', {}).values() if isinstance(job, dict)
        )

    def count_conditionals(self):
        return sum(len(re.findall(r'if:', file)) for file in self.yaml_files)

    def count_jobs(self):
        return sum(len(yaml_content.get('jobs', {})) for yaml_content in self.parsed_yaml if yaml_content)

    def count_env_vars(self):
        total_env_vars = 0
        global_env_vars = 0
        for yaml_content in self.parsed_yaml:
            if yaml_content and 'env' in yaml_content:
                global_env_vars += len(yaml_content['env'])
        for yaml_content in self.parsed_yaml:
            if yaml_content and 'jobs' in yaml_content:
                for job in yaml_content['jobs'].values():
                    if isinstance(job, dict):
                        job_env_vars = job.get('env', {})
                        for var in job_env_vars:
                            if var not in yaml_content.get('env', {}):
                                total_env_vars += 1
        return total_env_vars, global_env_vars

    def count_secrets(self):
        secret_pattern = re.compile(r'\${{\s*secrets\.(\w+)\s*}}')
        return sum(len(secret_pattern.findall(file)) for file in self.yaml_files)

    def count_jobs_excluded(self):
        return sum(1 for yaml_content in self.parsed_yaml if yaml_content
                   for job_details in yaml_content.get('jobs', {}).values()
                   if isinstance(job_details, dict) and 'if' in job_details)

    def count_jobs_allowed_to_fail(self):
        return sum(1 for yaml_content in self.parsed_yaml if yaml_content
                   for job_details in yaml_content.get('jobs', {}).values()
                   if isinstance(job_details, dict) and job_details.get('continue-on-error', False))

    def detect_tests(self):
        """Detects unit and integration tests in the pipeline."""
        unit_test_count = 0
        integration_test_count = 0
        any_test_count = 0

        unit_test_patterns = [
            r'mvn\s+.*?\btest\b',
            r'gradle\s+.*?\btest\b',
            r'pytest', r'yarn test', r'npm test',
            r'mvn\s+.*?\b(clean\s+package|install)\b',
            r'gradle\s+.*?\b(build)\b'
        ]
        integration_test_patterns = [
            r'mvn\s+.*?\bverify\b',
            r'gradle\s+.*?\bverify\b',
            r'e2e', r'end-to-end', r'acceptance', r'cypress', r'playwright'
        ]

        unit_test_name_patterns = re.compile(r'\b(unit|unittest|test|utest)\b', re.IGNORECASE)
        integration_test_name_patterns = re.compile(r'\b(functional|integration|e2e|end-to-end|acceptance)\b', re.IGNORECASE)

        for yaml_content in self.yaml_files:
            yaml_content_lower = yaml_content.lower()
            if re.search(r'-DskipTests', yaml_content_lower):
                continue

            has_unit_test = any(re.search(pattern, yaml_content_lower) for pattern in unit_test_patterns)
            has_integration_test = any(re.search(pattern, yaml_content_lower) for pattern in integration_test_patterns)

            if has_unit_test or has_integration_test:
                any_test_count += 1

            if has_unit_test:
                unit_test_count += 1

            if has_integration_test:
                integration_test_count += 1

        return {
            "unit_test_count": unit_test_count,
            "integration_test_count": integration_test_count,
            "any_test_count": any_test_count
        }

    def detect_phases(self):

        phase_patterns = {
            "build": re.compile(
                r'\bmvn\s+.*?\b(package|install)\b|'
                r'\bgradle\s+.*?\b(build)\b|'
                r'\bdotnet\s+.*?\b(build)\b|'
                r'\bmake\b|'
                r'\b(javac|ant|cmake)\b',
                re.IGNORECASE),

            "analyze": re.compile(
                r'\b(analyze|analysis|lint|checkstyle|spotbugs|findbugs|sonar|codeql|quality|pylint|eslint|flake8|bandit|mypy|rubocop|phpcs|staticcheck)\b',
                re.IGNORECASE),

            "deploy": re.compile(
                r'\bkubectl\s+.*?\b(apply|rollout)\b|'
                r'\bhelm\s+.*?\b(install|upgrade)\b|'
                r'\bterraform\s+.*?\b(apply)\b|'
                r'\bcloudfoundry\s+.*?\b(push)\b|'
                r'\bansible-playbook\b',
                re.IGNORECASE),

            "release": re.compile(
                r'\brelease\b|\bpublish\b|'
                r'\bmvn\s+.*?\b(deploy)\b|'
                r'\bgradle\s+.*?\b(publish)\b|'
                r'\bnpm\s+.*?\b(publish)\b|'
                r'\btwine\s+.*?\b(upload)\b|'
                r'\bdocker\s+.*?\b(push)\b|'
                r'\bgh\s+.*?\b(release)\b',
                re.IGNORECASE)
        }

        job_step_patterns = {
            "build": re.compile(r'\b(build|compile|package)\b', re.IGNORECASE),
            "analyze": re.compile(r'\b(analyze|lint|check|scan|quality)\b', re.IGNORECASE),
            "deploy": re.compile(r'\b(deploy|release|delivery)\b', re.IGNORECASE),
            "release": re.compile(r'\b(release|publish)\b', re.IGNORECASE),
        }

        phase_counts = {phase: 0 for phase in phase_patterns.keys()}

        for yaml_content in self.parsed_yaml:
            if yaml_content and 'jobs' in yaml_content:
                for job_name, job_details in yaml_content['jobs'].items():
                    job_steps = job_details.get('steps', [])

                    for phase in phase_patterns.keys():
                        # 🔍 **Check job name**
                        if job_step_patterns[phase].search(job_name):
                            phase_counts[phase] += 1
                            continue  # If found in job name, no need to check further

                        # 🔍 **Check step names**
                        for step in job_steps:
                            if isinstance(step, dict) and 'name' in step:
                                if job_step_patterns[phase].search(step['name']):
                                    phase_counts[phase] += 1
                                    break  # Stop checking steps if phase is already counted

                        # 🔍 **Check `run` commands**
                        if any(
                                isinstance(step, dict) and 'run' in step and phase_patterns[phase].search(step['run'])
                                for step in job_steps
                        ):
                            phase_counts[phase] += 1

        return phase_counts

    def get_metrics(self):
        """Extracts all pipeline metrics, including test detection."""
        test_metrics = self.detect_tests()
        phase_metrics = self.detect_phases()

        metrics = {
            "lines_of_code": self.count_lines_of_code(),
            "comments": self.count_comments(),
            "steps": self.count_steps(),
            "conditionals": self.count_conditionals(),
            "jobs": self.count_jobs(),
            "global_env_vars": self.count_env_vars()[1],
            "job_specific_env_vars": self.count_env_vars()[0],
            "secrets": self.count_secrets(),
            "jobs_excluded": self.count_jobs_excluded(),
            "jobs_allowed_to_fail": self.count_jobs_allowed_to_fail(),
            "unit_test_count": test_metrics["unit_test_count"],
            "integration_test_count": test_metrics["integration_test_count"],
            "any_test_count": test_metrics["any_test_count"],
            "build": phase_metrics["build"],
            "analyze": phase_metrics["analyze"],
            "deploy": phase_metrics["deploy"],
            "release": phase_metrics["release"]
        }
        return metrics
