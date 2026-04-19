import { MongoClient, ObjectId, Db } from 'mongodb';

const MONGODB_URI = process.env.MONGODB_URI;

let cached: { client: MongoClient; db: Db } | null = null;

function getClient(): { client: MongoClient; db: Db } {
  if (!MONGODB_URI) {
    throw new Error('MONGODB_URI environment variable is not set');
  }
  if (!cached) {
    const client = new MongoClient(MONGODB_URI);
    cached = { client, db: client.db('immo') };
  }
  return cached;
}

export function getDb(): Db {
  return getClient().db;
}

export function getMongoClient(): MongoClient {
  return getClient().client;
}

export { ObjectId };
