\getenv password DB_IAM_DB
CREATE ROLE smartgn_iam LOGIN PASSWORD :'password';
CREATE DATABASE iam_db OWNER smartgn_iam;
REVOKE CONNECT ON DATABASE iam_db FROM PUBLIC;

\getenv password DB_INSTALLATION_DB
CREATE ROLE smartgn_installation LOGIN PASSWORD :'password';
CREATE DATABASE installation_db OWNER smartgn_installation;
REVOKE CONNECT ON DATABASE installation_db FROM PUBLIC;

\getenv password DB_SMARTGN_SUPPORT_DB
CREATE ROLE smartgn_support LOGIN PASSWORD :'password';
CREATE DATABASE smartgn_support_db OWNER smartgn_support;
REVOKE CONNECT ON DATABASE smartgn_support_db FROM PUBLIC;

\getenv password DB_BILLING_DB
CREATE ROLE smartgn_billing LOGIN PASSWORD :'password';
CREATE DATABASE billing_db OWNER smartgn_billing;
REVOKE CONNECT ON DATABASE billing_db FROM PUBLIC;

\getenv password DB_SMARTGN_ALERTING_DB
CREATE ROLE smartgn_alerting LOGIN PASSWORD :'password';
CREATE DATABASE smartgn_alerting_db OWNER smartgn_alerting;
REVOKE CONNECT ON DATABASE smartgn_alerting_db FROM PUBLIC;

\getenv password DB_SMARTGN_MONITORING
CREATE ROLE smartgn_monitoring LOGIN PASSWORD :'password';
CREATE DATABASE smartgn_monitoring OWNER smartgn_monitoring;
REVOKE CONNECT ON DATABASE smartgn_monitoring FROM PUBLIC;

