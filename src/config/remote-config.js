import 'dotenv/config';

const settingNames = {
  'smartgn.gateway.iam-url': 'IAM_URL',
  'smartgn.gateway.installation-url': 'INSTALLATION_URL',
  'smartgn.gateway.support-url': 'SUPPORT_URL',
  'smartgn.gateway.billing-url': 'BILLING_URL',
  'smartgn.gateway.monitoring-url': 'MONITORING_URL',
  'smartgn.gateway.alerting-url': 'ALERTING_URL',
};

export async function loadRemoteConfig(env = process.env) {
  const address = env.SMARTGN_CONFIG_URL;
  if (!address) return {};

  const profile = encodeURIComponent(env.SMARTGN_CONFIG_PROFILE || 'local');
  const application = encodeURIComponent(env.SMARTGN_CONFIG_APPLICATION || 'api-gateway');
  let response;
  try {
    response = await fetch(`${address.replace(/\/$/, '')}/${application}/${profile}`, {
      signal: AbortSignal.timeout(3000),
      headers: { accept: 'application/json' },
    });
  } catch (error) {
    if (env.SMARTGN_CONFIG_REQUIRED === 'true') {
      throw new Error('Required SmartGN Config Server is unavailable', { cause: error });
    }
    return {};
  }

  if (!response.ok) {
    if (env.SMARTGN_CONFIG_REQUIRED === 'true') {
      throw new Error(`Required SmartGN Config Server returned ${response.status}`);
    }
    return {};
  }

  const document = await response.json();
  const source = document.propertySources?.[0]?.source ?? {};
  return Object.fromEntries(Object.entries(settingNames)
    .filter(([remoteName]) => typeof source[remoteName] === 'string')
    .map(([remoteName, localName]) => [localName, source[remoteName]]));
}
