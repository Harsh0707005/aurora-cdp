#!/usr/bin/env bash
# RDS Postgres for the serving / metadata layer. Private (not publicly accessible); reachable from the EC2 SG.
. "$(dirname "$0")/common.sh"; require RDS_IDENTIFIER RDS_PASSWORD
SG_NAME="$PROJECT-$ENV_NAME-rds"
VPC="${VPC_ID:-$(aws_ ec2 describe-vpcs --filters Name=isDefault,Values=true --query 'Vpcs[0].VpcId')}"
SG_ID=$(aws_ ec2 describe-security-groups --filters Name=group-name,Values="$SG_NAME" Name=vpc-id,Values="$VPC" --query 'SecurityGroups[0].GroupId' 2>/dev/null || true)
if [ -z "$SG_ID" ] || [ "$SG_ID" = "None" ]; then
  SG_ID=$(aws_ ec2 create-security-group --group-name "$SG_NAME" --description "aurora rds" --vpc-id "$VPC" --query GroupId)
  EC2_SG=$(aws_ ec2 describe-security-groups --filters Name=group-name,Values="$PROJECT-$ENV_NAME-ec2" --query 'SecurityGroups[0].GroupId' 2>/dev/null || true)
  if [ -n "$EC2_SG" ] && [ "$EC2_SG" != "None" ]; then
    aws_ ec2 authorize-security-group-ingress --group-id "$SG_ID" --protocol tcp --port 5432 --source-group "$EC2_SG"
  else log "EC2 SG not found yet; run 03_ec2_compose.sh then re-run this script to open 5432 to it"; fi
fi
if aws_ rds describe-db-instances --db-instance-identifier "$RDS_IDENTIFIER" >/dev/null 2>&1; then log "RDS $RDS_IDENTIFIER exists"; else
  log "creating RDS $RDS_IDENTIFIER ($RDS_INSTANCE_CLASS, ${RDS_STORAGE_GB}GB)"
  aws_ rds create-db-instance --db-instance-identifier "$RDS_IDENTIFIER" --db-instance-class "$RDS_INSTANCE_CLASS" \
    --engine postgres --engine-version 16 --allocated-storage "$RDS_STORAGE_GB" --storage-type gp3 --storage-encrypted \
    --master-username "$RDS_USERNAME" --master-user-password "$RDS_PASSWORD" --db-name "$RDS_DB_NAME" \
    --vpc-security-group-ids "$SG_ID" --no-publicly-accessible --backup-retention-period 7 --deletion-protection \
    --tags Key=Project,Value="$PROJECT" Key=Env,Value="$ENV_NAME" >/dev/null
fi
log "waiting for RDS to become available (can take ~10 min)"; aws_ rds wait db-instance-available --db-instance-identifier "$RDS_IDENTIFIER"
EP=$(aws_ rds describe-db-instances --db-instance-identifier "$RDS_IDENTIFIER" --query 'DBInstances[0].Endpoint.Address')
log "RDS endpoint: $EP:5432  (DATABASE_URL=postgresql://$RDS_USERNAME:***@$EP:5432/$RDS_DB_NAME)"
