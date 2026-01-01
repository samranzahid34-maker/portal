const mongoose = require('mongoose');
require('dotenv').config();

const MONGODB_URI = process.env.MONGODB_URI;

// Define Schemas locally to match server
const SourceSchema = new mongoose.Schema({
    _id: String,
    id: String,
    name: String,
    description: String,
    ownerId: String
});
const SourceModel = mongoose.model('Source', SourceSchema);

async function testPersistence() {
    try {
        console.log('Connecting...');
        await mongoose.connect(MONGODB_URI);

        console.log('1. Cleaning Sources...');
        await SourceModel.deleteMany({});

        const adminId = 'test-admin-123';

        console.log('2. Adding Sheet 1...');
        const sheet1 = {
            _id: 'sheet-1',
            id: 'google-id-1',
            name: 'Tab1',
            description: 'Sheet 1',
            ownerId: adminId
        };
        await SourceModel.create(sheet1);

        let count = await SourceModel.countDocuments();
        console.log(`   Count after Sheet 1: ${count}`);

        console.log('3. Adding Sheet 2...');
        const sheet2 = {
            _id: 'sheet-2',
            id: 'google-id-2', // Different ID
            name: 'Tab1',
            description: 'Sheet 2',
            ownerId: adminId
        };
        await SourceModel.create(sheet2);

        count = await SourceModel.countDocuments();
        console.log(`   Count after Sheet 2 (Diff ID): ${count}`);

        console.log('4. Adding Sheet 3 (Same Google ID, Diff Tab)...');
        const sheet3 = {
            _id: 'sheet-3',
            id: 'google-id-1', // SAME as Sheet 1
            name: 'Tab2',
            description: 'Sheet 1 - Tab 2',
            ownerId: adminId
        };
        await SourceModel.create(sheet3);

        count = await SourceModel.countDocuments();
        console.log(`   Count after Sheet 3: ${count}`);

        const all = await SourceModel.find({});
        console.log('   All Sources in DB:', JSON.stringify(all, null, 2));

        if (count === 3) {
            console.log('✅ PASS: Persistence works correctly. Atomic Create succeeds.');
        } else {
            console.log('❌ FAIL: Data lost.');
        }

    } catch (e) {
        console.error(e);
    } finally {
        await mongoose.disconnect();
    }
}

testPersistence();
