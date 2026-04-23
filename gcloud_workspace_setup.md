# Tutorial 0.1: Google Cloud Workspace Setup

In this tutorial, you will configure your local environment to interact with Google Cloud Platform (GCP). This setup ensures you are authenticated, targeting the correct project, and using the right credentials for local development.

---

## 1. Authenticate with Google Cloud

First, you need to authenticate your Google account with the `gcloud` CLI.

```bash
gcloud auth login
```

This command opens a browser window. Log in with your Google account and grant the necessary permissions.

---

## 2. List Available Projects

Before configuring your workspace, it is helpful to see which projects you have access to.

```bash
gcloud projects list
```

Identify the `PROJECT_ID` of the project you want to work on.

---

## 3. Initialize the Configuration

GCP uses "configurations" to manage different environments (e.g., separating development and production projects). We will initialize a new configuration or re-initialize an existing one.

```bash
gcloud init
```

When prompted:
1. Choose **Create a new configuration** (or select an existing one to update).
2. Enter a configuration name (e.g., `dev-environment` or `my-project-config`).
3. Choose the account you logged in with earlier.
4. Select the `PROJECT_ID` you found in step 2.
5. (Optional) Choose your default compute region and zone (e.g., `us-central1` and `us-central1-a`).

---

## 4. Set Application Default Credentials

If you are running code locally (like Python scripts using Google Cloud client libraries), you need Application Default Credentials (ADC). These are different from the user credentials used by `gcloud` commands.

```bash
gcloud auth application-default login
```

Assign the quota project to your current project. This ensures that API requests made from your local machine are billed and quota-checked against the correct project. Replace `<YOUR_PROJECT_ID>` with your actual Project ID.

```bash
gcloud auth application-default set-quota-project <YOUR_PROJECT_ID>
```

---

## 5. Manage and Clean Up Configurations

As you create and delete projects, you may need to manage your configurations to keep your workspace tidy.

### List all configurations

View your current active and inactive configurations:

```bash
gcloud config configurations list
```

### Create a new configuration manually

If you prefer to create a new configuration and switch projects without running the full interactive `gcloud init`:

```bash
gcloud config configurations create <NEW_CONFIG_NAME>
gcloud config configurations activate <NEW_CONFIG_NAME>
gcloud config set project <NEW_PROJECT_ID>
```

### Delete an obsolete configuration

When a project no longer exists or you no longer need the environment, you can remove its local configuration:

```bash
gcloud config configurations delete <OBSOLETE_CONFIG_NAME>
```

---

## Next steps

Now that your `gcloud` CLI and Application Default Credentials are set up, you are ready to proceed with the core project tutorials.
