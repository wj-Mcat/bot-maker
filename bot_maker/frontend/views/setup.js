var bot = new ChatSDK({
    config: {
      navbar: {
        title: 'BotMaker'
      },
      robot: {
        avatar: 'https://wechaty.js.org/img/chatbot-image.webp'
      },
      messages: [
        {
          type: 'text',
          content: {
            text: '智能助理为您服务，请问有什么可以帮您？'
          }
        }
      ]
    },
    requests: {
      send: function (msg) {
        if (msg.type === 'text') {
            return msg.content.cext
        }
      }
    }
  });
  
  bot.run();