# Splunk Apps Deployment Architecture
This is just an idea developed for Philips Electronics Nederland within the context of [JIRA ticket](https://splunk.atlassian.net/browse/FDSE-2571). To be extended and used at own risk.

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
        │   └── deployment.yml
        └── ses
            └── deployment.yml

```
* `apps/` Contains development for private apps
* `environments/` Contains
  * deployment instructions per each environment (`deployment.yml`)
  * specific apps configurations (e.g. `uat/es/app1`)
* `deploy.py` Used by the automation to perform the deployment

This repository follows the same structure. Please navigate it to verify its content.

### `deployment.yml`
As mentioned, these deployment files specify the apps and configurations needed on each specific environment. Example:
```yml
target:
  url: <deployment server URL>
apps:
  # Private apps
  app1:
    source: s3://apps/app1_1.0.0.tgz
    sha256: <sha from app>
    # If there are specific conf files to be added to this
    # app before being installed, config key will tell
    config:
      - ./app1/*.conf
  # Splunkbase apps
  cb-protection-app-for-splunk:
    source: s3://splunk_base/cb-protection-app-for-splunk_20.tgz
    sha256: 6c20f79fb606aac0be0e705ce5a5a84b526692be74442a543c06ecc1e36095af
```

## CI/CD Automation
Two pipelines:
* `package` Triggered on merged PR to `main` when there are changes to `apps/*`
  * Will package apps with changes and upload them into an AWS S3 bucket
    > Apps versions bumps are expected to be done at PR opening
* `deploy` Triggered on merged PR to `main` when there are changes to `environments/*`
  * Will read the deployment configuration and run the `deploy.py` script to gather the app(s), eventually re-package with proper configuration and install in the target URL
  * Will create `env_deployment_report.json` with information about cloud validation and deployment status

`package_simple` is a simpler pipeline alternative to `package` with packaging performed by `tar`.

## Technical Notes
* Pipelines triggers could differ from the suggested ones depending on the branches used
* New pipelines could integrate AppInspect execution via dedicated action(s)
* `deployment.yml` could have more parameters, the suggested ones are the bare minimum
* Remember: the main concept is keeping development and configurations separated!
* Be inspired by this solution! No need to apply revolutionary changes to the current architecture, maybe only a couple of them would be enough

### Learn More
* [Splunk Cloud ACS API](https://docs.splunk.com/Documentation/SplunkCloud/9.2.2406/Config/ACSIntro)
* [AppInspect CLI Action](https://github.com/splunk/appinspect-cli-action)
* [AppInspect API Action](https://github.com/splunk/appinspect-api-action)
* [Anatomy of Splunk Apps](https://dev.splunk.com/enterprise/docs/developapps/createapps/appanatomy/) - Highly recommended read to **clarify any doubts about usage of `default/` and `local/` directories** in Splunk Apps.