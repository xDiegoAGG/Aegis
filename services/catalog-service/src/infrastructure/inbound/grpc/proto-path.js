import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

export function getProtoPath(filename) {
  if (process.env.PROTO_DIR) {
    return path.join(process.env.PROTO_DIR, filename);
  }
  return path.resolve(__dirname, "../../../../../../shared/proto", filename);
}
