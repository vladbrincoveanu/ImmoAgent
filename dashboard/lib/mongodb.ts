import { MongoClient, ObjectId, Db } from 'mongodb';

const MONGODB_URI = process.env.MONGODB_URI!;

let cached = (global as { mongodb?: { client: MongoClient; db: Db } }).mongodb;

if (!cached) {
  const client = new MongoClient(MONGODB_URI);
  cached = { client, db: client.db('immo') };
  (global as { mongodb?: typeof cached }).mongodb = cached;
}

export const { client, db } = cached;
export { ObjectId };
