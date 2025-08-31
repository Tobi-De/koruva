# Falco Template repository

This GitHub [template repository](https://docs.github.com/en/github/creating-cloning-and-archiving-repositories/creating-a-repository-on-github/creating-a-repository-from-a-template) can be used to create a new falco project, based on [https://github.com/falcopackages/starter-template](https://github.com/falcopackages/starter-template).

> [!WARNING]
> Project are currently generated using the `next-release` branch.

[![Generate a new project](https://img.shields.io/badge/Generate%20a%20new%20project-blue?style=for-the-badge)](https://github.com/falcopackages/falco-template-repository/generate) 

Add a one-line description of your repository, then click "Create repository from template".

![image](https://github.com/user-attachments/assets/2f43ce91-0a11-4dc7-a274-bd4f30dafffb)

Once created, your new repository will execute a GitHub Actions workflow that uses falco-cli to rewrite the repository to the desired state. This make take 30 seconds or so.

> [!IMPORTANT]
> It's not currently possible to override the `.github` folder without using a personal access token. Therefore, there will be a `.rename_to_.github` folder that you need to rename to `.github`. You can do it manually, but it will be done automatically the first time you run `just setup` to set up the project locally.
