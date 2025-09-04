# System Design

## Repository Architecture
```
.
├── README.md
├── .github
│   └── workflows
│        ├── deploy.yml
│        ├── manual_deploy.yml
│        └── package.yml
├── apps
│   └── app1
│       ├── app.manifest
│       └── default
│           ├── collections.conf
│           └── logging.conf
├── deploy.py
├── modules
│   ├── apps_processing.py
│   ├── report_generator.py
│   └── splunk_cloud.py
└── environments
    ├── prod
    │   ├── es
    │   │   └── deployment.yml
    │   └── stg
    │       └── deployment.yml
    └── test
        ├── es
        │   ├── app1
        │   │   └── logging.conf
        |   |   └── local.meta
        │   └── deployment.yml
        └── stg
            └── deployment.yml

```
* `.github/` Contains github workflows which are the logic for packaging, uploading and deploying automation
* `apps/` Contains development for private apps
* `environments/` Contains
  * deployment instructions per each environment (`deployment.yml`)
  * specific apps configurations (e.g. `uat/es/app1`)
* `deploy.py` Used by the automation to perform the deployment
* `modules/` Contains methods used in deployment automation

This repository follows the same structure. Please navigate it to verify its content.

### `deployment.yml`
As mentioned, these deployment files specify the apps and configurations needed on each specific environment. Example:
```yml
target:
  url: https://admin.splunk.com/{stack}
  experience: <victoria|classic>
apps:
  # Private apps
  # - Leave empty if target does not need private apps
  app1:
    s3-bucket: bucket-1
    source: apps/app1.tgz
    # If there are specific conf files to be added to this
    # app before being installed, config key will tell
    config:
      - ./app1/*.conf
splunkbase-apps:
  # Splunkbase apps
  # - Leave empty if target does not need private apps
  Cb Protection App for Splunk:
    version: 1.0.0
```

## CI/CD Automation
Two main pipelines:
* `package` Triggered on merged PR to `main` when there are changes to `apps/*`:
  * Will package apps with changes and upload them into an AWS S3 bucket
    > Apps versions bumps are expected to be done at PR opening
* `deploy` Triggered on merged PR to `main` when there are changes to `environments/*`:
  * Will read the deployment configuration and run the `deploy.py` script to gather the app(s), eventually re-package with proper configuration and install in the target URL
  * Will create `env_deployment_report.json` with information about cloud validation and deployment status. Example report: [example_deployment_report.json](https://github.com/splunk/Splunk-Apps-Deployment-Architecture/blob/main/example_deployment_report.json)

> The `manual_deploy` pipeline has the same functionality as the `deploy` one but it can be manually triggered