import { GetCommand, ScanCommand } from "@aws-sdk/lib-dynamodb";
import { Book } from "../../../domain/entities/Book.js";
import { BookRepository } from "../../../application/ports/out/BookRepository.js";

export class DynamoBookRepository extends BookRepository {
  constructor({ docClient, tableName }) {
    super();
    this.docClient = docClient;
    this.tableName = tableName;
  }

  async findAll() {
    const result = await this.docClient.send(
      new ScanCommand({ TableName: this.tableName })
    );
    return (result.Items || []).map((item) => new Book(item));
  }

  async findById(id) {
    const result = await this.docClient.send(
      new GetCommand({ TableName: this.tableName, Key: { id } })
    );
    return result.Item ? new Book(result.Item) : null;
  }
}
