const mongoose = require('mongoose');
require('dotenv').config();

const MONGODB_URI = process.env.MONGODB_URI;

if (!MONGODB_URI) {
    console.error('❌ MONGODB_URI not found in .env');
    process.exit(1);
}

async function clearData() {
    try {
        console.log('Connecting to MongoDB...');
        await mongoose.connect(MONGODB_URI);
        console.log('✓ Connected');

        // Access native collections to be sure we hit them even if schemas changed
        const collections = await mongoose.connection.db.listCollections().toArray();
        const collectionNames = collections.map(c => c.name);

        if (collectionNames.includes('admins')) {
            await mongoose.connection.collection('admins').deleteMany({});
            console.log('✓ Cleared "admins"');
        }

        if (collectionNames.includes('registrations')) {
            await mongoose.connection.collection('registrations').deleteMany({});
            console.log('✓ Cleared "registrations"');
        }

        if (collectionNames.includes('sources')) {
            await mongoose.connection.collection('sources').deleteMany({});
            console.log('✓ Cleared "sources"');
        }

        console.log('✅ Database cleaned successfully.');
    } catch (error) {
        console.error('Error clearing data:', error);
    } finally {
        await mongoose.disconnect();
        process.exit(0);
    }
}

clearData();
