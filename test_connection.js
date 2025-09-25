const mineflayer = require('mineflayer');

function createBot() {
  const bot = mineflayer.createBot({
    host: 'east.donutsmp.net',
    port: 25565,
    username: 'mnidia0811@gmail.com', // Your Microsoft email
    version: '1.21.5',
    auth: 'microsoft', // Use Microsoft authentication
    checkTimeoutInterval: 30000,
    hideErrors: false,
    onMsaCode: (data) => {
      console.log('🔐 Microsoft Authentication Required');
      console.log('📱 Please visit the following URL to authenticate:');
      console.log(`🌐 ${data.verification_uri}`);
      console.log('🔢 Enter this device code when prompted:');
      console.log(`📋 ${data.user_code}`);
      console.log('⏰ You have 15 minutes to complete authentication');
      console.log('🔄 Waiting for authentication...');
    }
  });

  bot.on('login', () => {
    console.log('✅ Successfully authenticated with Microsoft!');
    console.log(`Logged in as ${bot.username} (${bot.uuid})`);
    
    // Send login command after joining
    setTimeout(() => {
      bot.chat('/w DrGlaze Hello');
      console.log('🔑 Sent login command');
    }, 2000);
  });

  // Handle chat messages
  bot.on('message', (message) => {
    const msg = message.toString().trim();
    console.log(`💬 [Chat] ${msg}`);
  });

  // Handle errors
  bot.on('error', (err) => {
    console.error('❌ Error:', err.message);
    if (err.stack) {
      console.error(err.stack);
    }
  });

  // Handle disconnection
  bot.on('end', (reason) => {
    console.log(`🔌 Disconnected: ${reason}`);
    console.log('Attempting to reconnect in 10 seconds...');
    setTimeout(createBot, 10000);
  });

  // Handle spawn
  bot.on('spawn', () => {
    console.log('🌍 Spawned in the world');
  });

  // Handle server kick
  bot.on('kicked', (reason) => {
    console.log(`👢 Kicked: ${reason}`);
  });
}

console.log('🔌 Starting Microsoft authentication...');
createBot();