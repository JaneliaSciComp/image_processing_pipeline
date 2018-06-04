'use strict';
var ObjectId = require('mongodb').ObjectID;
module.exports.id = "FIRST";

module.exports.up = function (done) {
  var steps = this.db.collection('step');
  var params = this.db.collection('parameter');
  var dependency = this.db.collection('dependency');
  
  // Remove dependencies with unknown input and output paramters
  dependency.remove({ "inputField" : { $eq: ObjectId("5b12047ea275276dec9a2eb9") } })
  dependency.remove({ "inputField" : { $eq: ObjectId("5b12048ba275276dec9a2eba") } })
  dependency.remove({ "outputField" : { $eq: ObjectId("5ab504e8a275271626e415df") } })
  dependency.remove({ "outputField" : { $eq: ObjectId("5ab504f6a275271626e415e0") } })

  //coll.insert({ name: 'antje', text1: 'antjes text' }, done);
  done();
};

module.exports.down = function (done) {
  // use this.db for MongoDB communication, and this.log() for logging
  done();
};