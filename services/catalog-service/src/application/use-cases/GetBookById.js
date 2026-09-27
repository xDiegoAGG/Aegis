import { BookNotFoundError } from "../../domain/errors/BookNotFoundError.js";

export class GetBookById {
  constructor(bookRepository) {
    this.bookRepository = bookRepository;
  }

  async execute(id) {
    const book = await this.bookRepository.findById(id);
    if (!book) throw new BookNotFoundError(id);
    return book;
  }
}
