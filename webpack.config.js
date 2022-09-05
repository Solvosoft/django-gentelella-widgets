const path = require('path');

module.exports = {
  entry: { gentelella: './assets/index.js' },  // path to our input file
  output: {
    filename: '[name]-bundle.js',  // output bundle file name
    path: path.resolve(__dirname, './djgentelella/static/gentelella/js/'),  // path to our Django static directory
  },
    module: {
    rules: [
      {
        test: /\.(scss)$/,
        use: [
          {
            loader: 'style-loader'
          },
          {
            loader: 'css-loader'
          },
          {
            loader: 'postcss-loader',
            options: {
              postcssOptions: {
                plugins: () => [
                  require('autoprefixer')
                ]
              }
            }
          },
          {
            loader: 'sass-loader'
          }
        ]
      }
    ]
  }
};
