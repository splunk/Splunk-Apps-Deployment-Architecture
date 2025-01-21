# Splunk Apps Deployment Architecture
This is just an idea developed within the context of [JIRA ticket](https://splunk.atlassian.net/browse/FDSE-2571). To be extended and used at own risk.

Assumptions:
* All apps are stored into a single GitHub repository
* Deployment performed by custom scripts
* Automation provided by GitHub Actions

## Repo Architecture
```
.
├── README.md
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
│   └── splunkcloud.py
└── environments
    ├── prod
    │   ├── es
    │   │   └── deployment.yml
    │   └── ses
    │       └── deployment.yml
    └── uat
        ├── es
        │   ├── app1
        │   │   └── logging.conf
        |   |   └── local.meta
        │   └── deployment.yml
        └── ses
            └── deployment.yml

```
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
  url: <deployment server URL>
  experience: <victoria|classic>
apps:
  # Private apps
  app1:
    s3-bucket: bucket-1
    source: apps/app1.tgz
    # If there are specific conf files to be added to this
    # app before being installed, config key will tell
    config:
      - ./app1/*.conf
splunkbase-apps:
  # Splunkbase apps
  cb-protection-app-for-splunk:
    version: 1.0.0
```

## CI/CD Automation
Two pipelines:
* `package` Triggered on merged PR to `main` when there are changes to `apps/*`
  * Will package apps with changes and upload them into an AWS S3 bucket
    > Apps versions bumps are expected to be done at PR opening
* `deploy` Triggered on merged PR to `main` when there are changes to `environments/*`
  * Will read the deployment configuration and run the `deploy.py` script to gather the app(s), eventually re-package with proper configuration and install in the target URL
  * Will create `env_deployment_report.json` with information about cloud validation and deployment status

## Technical Notes
* Pipelines triggers could differ from the suggested ones depending on the branches used
* New pipelines could integrate AppInspect execution via dedicated action(s)
* `deployment.yml` could have more parameters, the suggested ones are the bare minimum
* Remember: the main concept is keeping development and configurations separated!
* Be inspired by this solution! No need to apply revolutionary changes to the current architecture, maybe only a couple of them would be enough

## Limitations
* Splunkbase apps MUST be installed from Splunkbase on Splunk Cloud environments. ACS API can be leveraged to automatically install Splunkbase apps, but:
  - Splunkbase apps **cannot be installed from S3** because of App ID conflicts (they are not private apps!)
  - Splunkbase apps **cannot be installed with a custom configuration**; once installed, they will have to be configured via UI or by calling other APIs

### Learn More
* [Splunk Cloud ACS API](https://docs.splunk.com/Documentation/SplunkCloud/9.2.2406/Config/ACSIntro)
* [AppInspect CLI Action](https://github.com/splunk/appinspect-cli-action)
* [AppInspect API Action](https://github.com/splunk/appinspect-api-action)
* [Anatomy of Splunk Apps](https://dev.splunk.com/enterprise/docs/developapps/createapps/appanatomy/) - Highly recommended read to **clarify any doubts about usage of `default/` and `local/` directories** in Splunk Apps.