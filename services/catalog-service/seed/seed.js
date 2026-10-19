// Creates the books table if it does not exist and fills it with the catalog data.
// Safe to run many times: every run writes the same 50 items with the same values.
// Run inside the cluster as the Job in kubernetes/seed-books-job.yaml.
import { readFile } from "node:fs/promises";
import {
  CreateTableCommand,
  DescribeTableCommand,
  waitUntilTableExists,
} from "@aws-sdk/client-dynamodb";
import { BatchWriteCommand } from "@aws-sdk/lib-dynamodb";
import { dynamoDbClient, docClient } from "../src/infrastructure/config/dynamo.js";

const TABLE_NAME = process.env.BOOKS_TABLE || "tb_books";
const TOTAL_BOOKS = 50;
const BATCH_SIZE = 25; // DynamoDB limit per BatchWrite
const CONNECT_ATTEMPTS = 30;
const AUTHORS = [
  "Gabriel García Márquez",
  "Isabel Allende",
  "Jorge Luis Borges",
  "Julio Cortázar",
  "Mario Vargas Llosa",
];

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

// Waits until DynamoDB answers, then creates the table if it is missing.
async function ensureTable() {
  for (let attempt = 1; attempt <= CONNECT_ATTEMPTS; attempt++) {
    try {
      await dynamoDbClient.send(new DescribeTableCommand({ TableName: TABLE_NAME }));
      console.log("Table", TABLE_NAME, "already exists");
      return;
    } catch (error) {
      if (error.name === "ResourceNotFoundException") {
        await dynamoDbClient.send(
          new CreateTableCommand({
            TableName: TABLE_NAME,
            KeySchema: [{ AttributeName: "id", KeyType: "HASH" }],
            AttributeDefinitions: [{ AttributeName: "id", AttributeType: "S" }],
            BillingMode: "PAY_PER_REQUEST",
          })
        );
        await waitUntilTableExists({ client: dynamoDbClient, maxWaitTime: 60 }, { TableName: TABLE_NAME });
        console.log("Table", TABLE_NAME, "created");
        return;
      }
      console.log("DynamoDB not ready (attempt", attempt, "of", CONNECT_ATTEMPTS + "):", error.name);
      await sleep(2000);
    }
  }
  throw new Error("DynamoDB did not answer after " + CONNECT_ATTEMPTS + " attempts");
}

// The 6 books of the original store plus test books up to 50, so the Scan has real weight.
// Test books use fixed values (no random) so every environment gets the same table.
async function buildBooks() {
  const books = JSON.parse(await readFile(new URL("./books.json", import.meta.url), "utf8"));
  for (let i = books.length + 1; i <= TOTAL_BOOKS; i++) {
    books.push({
      id: String(i),
      name: "Test book #" + i,
      author: AUTHORS[i % AUTHORS.length],
      description: "Description generated for Aegis load tests.",
      price: 10000 + ((i * 7919) % 70000),
      countInStock: (i * 37) % 101,
      image: "https://via.placeholder.com/150",
    });
  }
  return books;
}

async function writeBooks(books) {
  for (let start = 0; start < books.length; start += BATCH_SIZE) {
    let requests = [];
    for (const book of books.slice(start, start + BATCH_SIZE)) {
      requests.push({ PutRequest: { Item: book } });
    }
    // Retry the items DynamoDB could not write in this call
    while (requests.length > 0) {
      const result = await docClient.send(
        new BatchWriteCommand({ RequestItems: { [TABLE_NAME]: requests } })
      );
      requests = (result.UnprocessedItems && result.UnprocessedItems[TABLE_NAME]) || [];
      if (requests.length > 0) {
        await sleep(500);
      }
    }
  }
}

async function main() {
  await ensureTable();
  const books = await buildBooks();
  await writeBooks(books);
  console.log("Seeded", books.length, "books into", TABLE_NAME);
}

main().catch((error) => {
  console.error("Seed failed:", error);
  process.exit(1);
});
