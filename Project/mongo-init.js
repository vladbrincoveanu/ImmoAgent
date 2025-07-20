// MongoDB initialization script for home.ai

// Switch to the immo database
db = db.getSiblingDB('immo');

// Create collections
db.createCollection('listings');
db.createCollection('users');

// Create indexes for better performance
db.listings.createIndex({ "url": 1 }, { unique: true });
db.listings.createIndex({ "source": 1 });
db.listings.createIndex({ "bezirk": 1 });
db.listings.createIndex({ "price_total": 1 });
db.listings.createIndex({ "area_m2": 1 });
db.listings.createIndex({ "processed_at": -1 });
db.listings.createIndex({ "score": -1 });

db.users.createIndex({ "username": 1 }, { unique: true });
db.users.createIndex({ "email": 1 }, { unique: true });

// Create admin user if it doesn't exist
var adminUser = db.users.findOne({ "username": "admin" });
if (!adminUser) {
    // Note: Password will be hashed by the application
    db.users.insertOne({
        username: "admin",
        email: "admin@home.ai",
        password_hash: "temporary_hash_will_be_replaced",
        role: "admin",
        created_at: new Date(),
        last_login: null
    });
    print("Admin user placeholder created");
}

print("MongoDB initialization completed"); 