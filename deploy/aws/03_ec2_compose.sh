#!/usr/bin/env bash
# One EC2 host (Amazon Linux 2023) running the docker-compose stack. User-data installs docker + compose, clones
# nothing (the repo tarball is uploaded by 04_deploy_code.sh), and leaves a systemd unit for the stack.
. "$(dirname "$0")/common.sh"; require EC2_KEY_NAME
SG_NAME="$PROJECT-$ENV_NAME-ec2"
VPC="${VPC_ID:-$(aws_ ec2 describe-vpcs --filters Name=isDefault,Values=true --query 'Vpcs[0].VpcId')}"
SUBNET="${SUBNET_ID:-$(aws_ ec2 describe-subnets --filters Name=vpc-id,Values="$VPC" Name=default-for-az,Values=true --query 'Subnets[0].SubnetId')}"
SG_ID=$(aws_ ec2 describe-security-groups --filters Name=group-name,Values="$SG_NAME" Name=vpc-id,Values="$VPC" --query 'SecurityGroups[0].GroupId' 2>/dev/null || true)
if [ -z "$SG_ID" ] || [ "$SG_ID" = "None" ]; then
  SG_ID=$(aws_ ec2 create-security-group --group-name "$SG_NAME" --description "aurora ec2" --vpc-id "$VPC" --query GroupId)
  aws_ ec2 authorize-security-group-ingress --group-id "$SG_ID" --protocol tcp --port 22 --cidr "$ALLOWED_CIDR"
  aws_ ec2 authorize-security-group-ingress --group-id "$SG_ID" --protocol tcp --port 8000 --cidr "$ALLOWED_CIDR"
fi
ROLE="$PROJECT-$ENV_NAME-ec2-role"
if ! aws_ iam get-role --role-name "$ROLE" >/dev/null 2>&1; then
  aws_ iam create-role --role-name "$ROLE" --assume-role-policy-document '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"ec2.amazonaws.com"},"Action":"sts:AssumeRole"}]}' >/dev/null
  aws_ iam put-role-policy --role-name "$ROLE" --policy-name s3-landing --policy-document "{\"Version\":\"2012-10-17\",\"Statement\":[{\"Effect\":\"Allow\",\"Action\":[\"s3:ListBucket\"],\"Resource\":\"arn:aws:s3:::$RAW_BUCKET\"},{\"Effect\":\"Allow\",\"Action\":[\"s3:GetObject\",\"s3:PutObject\"],\"Resource\":\"arn:aws:s3:::$RAW_BUCKET/*\"}]}"
  aws_ iam attach-role-policy --role-name "$ROLE" --policy-arn arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore
  aws_ iam create-instance-profile --instance-profile-name "$ROLE" >/dev/null
  aws_ iam add-role-to-instance-profile --instance-profile-name "$ROLE" --role-name "$ROLE"
  sleep 10
fi
AMI=$(aws_ ssm get-parameter --name "$EC2_AMI_SSM" --query 'Parameter.Value')
EXISTING=$(aws_ ec2 describe-instances --filters Name=tag:Name,Values="$PROJECT-$ENV_NAME" Name=instance-state-name,Values=pending,running --query 'Reservations[0].Instances[0].InstanceId' 2>/dev/null || true)
if [ -n "$EXISTING" ] && [ "$EXISTING" != "None" ]; then log "instance $EXISTING already running"; IID=$EXISTING; else
  log "launching $EC2_INSTANCE_TYPE from $AMI"
  IID=$(aws_ ec2 run-instances --image-id "$AMI" --instance-type "$EC2_INSTANCE_TYPE" --key-name "$EC2_KEY_NAME" \
    --security-group-ids "$SG_ID" --subnet-id "$SUBNET" --iam-instance-profile Name="$ROLE" \
    --block-device-mappings 'DeviceName=/dev/xvda,Ebs={VolumeSize=50,VolumeType=gp3,Encrypted=true}' \
    --user-data file://"$(dirname "$0")/user_data.sh" \
    --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=$PROJECT-$ENV_NAME},{Key=Project,Value=$PROJECT},{Key=Env,Value=$ENV_NAME}]" \
    --query 'Instances[0].InstanceId')
  aws_ ec2 wait instance-running --instance-ids "$IID"
fi
IP=$(aws_ ec2 describe-instances --instance-ids "$IID" --query 'Reservations[0].Instances[0].PublicIpAddress')
log "instance $IID public ip $IP ; next: ./04_deploy_code.sh $IP"
