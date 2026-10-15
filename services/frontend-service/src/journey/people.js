import { SCENARIOS } from './scenarios';
import { SENDERS } from '../utils/dataGenerator';

const KNOWN = {};
SCENARIOS.forEach((sc) => {
  KNOWN[sc.sender.id] = sc.sender.name;
});
SENDERS.forEach((s) => {
  KNOWN[s.id] = s.name;
});

/** Nome legível de uma conta. O user-service cria contas novas com o nome "User <id>". */
export function friendlyName(userId, apiName) {
  if (KNOWN[userId]) return KNOWN[userId];
  if (apiName && !/^User\s/.test(apiName)) return apiName;
  return userId;
}
