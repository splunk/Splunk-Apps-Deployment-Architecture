# Splunk Apps Deployment Architecture
This is an idea developed within the context of [this engagement](https://splunk.atlassian.net/browse/FDSE-2571). To be extended and used at own risk.

This project is part of [DEV1362](https://conf.splunk.com/sessions/catalog.html?search=DEV1362#) Technical Session at <img src="https://conf.splunk.com/content/dam/splunk-conf/2025/conf25logo.svg" width=50 alt=".conf25"> 

### Assumptions:
* All apps are stored into a single GitHub repository
* Deployment performed by custom scripts
* Automation provided by GitHub Actions

## Getting Started
1. Fork and clone this repository
2. Add custom apps files in `apps/` directory
3. Add environment configuration files in `environments/`
4. Add environment names into `deploy.yml` matrix
5. In Github, add secrets to repository, in particular:
- `AWS_ACCESS_KEY_ID`,
- `AWS_SECRET_ACCESS_KEY`,
- `AWS_REGION` (of S3 Bucket),
- `SPLUNK_USERNAME` (for `splunk.com` account)
- `SPLUNK_PASSWORD` (for `splunk.com` account)
- `SPLUNK_TOKEN_{INSTANCE_ID}` (e.g. `SPLUNK_TOKEN_TEST_ES`, one token for each instance)
> Splunk Tokens can be created either using UI or REST API: [documentation](https://help.splunk.com/en/splunk-enterprise/administer/manage-users-and-security/9.4/authenticate-into-the-splunk-platform-with-tokens/create-authentication-tokens)
6. Make changes to apps and/or environment configration, merge changes and enjoy the running automation!

## Repository Architecture
Check: [SYSTEM_DESIGN.md](https://github.com/splunk/Splunk-Apps-Deployment-Architecture/blob/main/SYSTEM_DESIGN.md)

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