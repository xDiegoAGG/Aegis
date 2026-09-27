import grpc from "@grpc/grpc-js";
import protoLoader from "@grpc/proto-loader";
import { getProtoPath } from "./proto-path.js";
import { BookNotFoundError } from "../../../domain/errors/BookNotFoundError.js";

const PROTO_PATH = getProtoPath("catalog.proto");

const packageDef = protoLoader.loadSync(PROTO_PATH, {
  keepCase: true,
  longs: String,
  enums: String,
  defaults: true,
  oneofs: true,
});
const catalogProto = grpc.loadPackageDefinition(packageDef).catalog;

const toGrpcBook = (book) => ({
  id: String(book.id ?? ""),
  name: String(book.name ?? ""),
  author: String(book.author ?? ""),
  description: String(book.description ?? ""),
  price: String(book.price ?? ""),
  countInStock: Number(book.countInStock ?? 0),
  image: String(book.image ?? ""),
});

export function startGrpcServer({ listBooks, getBookById, port }) {
  const server = new grpc.Server();

  server.addService(catalogProto.CatalogService.service, {
    ListBooks: async (_call, callback) => {
      try {
        const books = await listBooks.execute();
        callback(null, { books: books.map(toGrpcBook) });
      } catch (err) {
        callback(err);
      }
    },
    GetBook: async (call, callback) => {
      try {
        const book = await getBookById.execute(call.request.id);
        callback(null, toGrpcBook(book));
      } catch (err) {
        if (err instanceof BookNotFoundError) {
          return callback({
            code: grpc.status.NOT_FOUND,
            message: err.message,
          });
        }
        callback(err);
      }
    },
  });

  server.bindAsync(
    `0.0.0.0:${port}`,
    grpc.ServerCredentials.createInsecure(),
    (err) => {
      if (err) {
        console.error("gRPC bind failed", err);
        return;
      }
      console.log(`gRPC server listening on ${port}`);
    }
  );

  return server;
}
