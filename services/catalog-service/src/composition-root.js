import { docClient } from "./infrastructure/config/dynamo.js";
import { DynamoBookRepository } from "./infrastructure/outbound/persistence/DynamoBookRepository.js";
import { ListBooks } from "./application/use-cases/ListBooks.js";
import { GetBookById } from "./application/use-cases/GetBookById.js";

const tableName = process.env.BOOKS_TABLE || "tb_books";

const bookRepository = new DynamoBookRepository({ docClient, tableName });

export const useCases = {
  listBooks: new ListBooks(bookRepository),
  getBookById: new GetBookById(bookRepository),
};
