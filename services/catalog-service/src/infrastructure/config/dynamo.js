import "dotenv/config";
import { DynamoDBClient } from "@aws-sdk/client-dynamodb";
import { DynamoDBDocumentClient } from "@aws-sdk/lib-dynamodb";
import { fromEnv } from "@aws-sdk/credential-providers";

const region = process.env.AWS_REGION || "us-east-1";
const localEndpoint = process.env.DYNAMODB_ENDPOINT;
const config = { region };

if (localEndpoint) {
  config.endpoint = localEndpoint;
  config.credentials = {
    accessKeyId: process.env.AWS_ACCESS_KEY_ID || "local",
    secretAccessKey: process.env.AWS_SECRET_ACCESS_KEY || "local",
  };
} else if ((process.env.NODE_ENV || "dev") !== "production") {
  config.credentials = fromEnv();
}

export const dynamoDbClient = new DynamoDBClient(config);
export const docClient = DynamoDBDocumentClient.from(dynamoDbClient);
