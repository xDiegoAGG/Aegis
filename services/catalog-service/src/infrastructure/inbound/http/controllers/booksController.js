import { BookNotFoundError } from "../../../../domain/errors/BookNotFoundError.js";

export const makeBooksController = ({ listBooks, getBookById }) => ({
  list: async (_req, res, next) => {
    try {
      const books = await listBooks.execute();
      res.json(books);
    } catch (err) {
      next(err);
    }
  },

  detail: async (req, res, next) => {
    try {
      const book = await getBookById.execute(req.params.id);
      res.json(book);
    } catch (err) {
      if (err instanceof BookNotFoundError) {
        return res.status(404).json({ message: err.message });
      }
      next(err);
    }
  },
});
