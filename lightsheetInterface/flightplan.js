var plan = require('flightplan');

var config = {
  srcDir: '/opt/dev/lightsheetInterfaceDraft/lightsheetInterface',  // location on the local server
  projectDir: '/opt/projects/lightsheet',  // location on the local server
  pythonPath: '/usr/bin/python3',
  keepReleases: 3,
  username: 'ackermand',
};

plan.target('local', {
  host: 'localhost',
  username: config.username,
  agent: process.env.SSH_AUTH_SOCK
  },{
    // Shouldn't be overridden, so please don't try.
    gitCheck: true
});

plan.target('staging', {
  host: 'lightsheet',
  username: config.username,
  agent: process.env.SSH_AUTH_SOCK
  },{
    // Shouldn't be overridden, so please don't try.
    gitCheck: true
});

plan.target('test', {
  host: 'pipeline-test',
  username: config.username,
  agent: process.env.SSH_AUTH_SOCK
  },{
    // Shouldn't be overridden, so please don't try.
    gitCheck: true
});

plan.target('production', {
  host: 'pipeline',
  username: config.username,
  agent: process.env.SSH_AUTH_SOCK
  },{
    // Shouldn't be overridden, so please don't try.
    gitCheck: true
});

plan.target('test-new', {
  host: 'pipeline-test-new',
  username: config.username,
  agent: process.env.SSH_AUTH_SOCK
  },{
    // Shouldn't be overridden, so please don't try.
    gitCheck: true
});

plan.target('production-new', {
  host: 'pipeline-new',
  username: config.username,
  agent: process.env.SSH_AUTH_SOCK
  },{
    // Shouldn't be overridden, so please don't try.
    gitCheck: false
});

plan.local('version', function(local) {
  local.log('create new version number and add as a git commit')
  var versionType = plan.runtime.options.argv.remain[1];
  var command = local.exec('npm version ' + versionType);
  var command = local.exec('cat package.json | grep version');
  var myVersion =  "v" + (JSON.stringify(command).split(':')[3]).split('"')[1].replace('\\','');
  var command = local.exec('git add package.json; git commit -m' + '"' + myVersion + '"');
});

// Check if there are files that have not been committed to git. This stops
// us from deploying code in an inconsistent state. It also prevents slapdash
// changes from being deployed without a log of who added them in github. Not
// fool proof, but better than nothing.
plan.local('deploy', function(local) {
  if (plan.runtime.target === 'production' || plan.runtime.options.gitCheck) {
    local.log('checking git status...');
    var result = local.exec('git status --porcelain', {silent: true});

    if (result.stdout) {
      local.log(result.stdout);
      plan.abort('Uncommited files found, see list above');
    }
  } else {
    local.log('skipping git check!!!');
  }
});


plan.local('deploy', function(local) {
  config.deployTo = config.projectDir + '/releases/' + (new Date().getTime());
  local.log('Creating webroot');
  local.exec('mkdir -p ' + config.deployTo);
});

// Gets a list of files that git knows about and sends them to the
// target.
plan.local('deploy', function (local) {
  local.log('Transferring website files');
  var files = local.git('ls-files', {silent: true});
  local.transfer(files, config.deployTo + '/');
});

plan.local('deploy',function (local) {
  local.log('Linking to new release');
  local.exec('ln -nfs ' + config.deployTo + ' ' +
    config.projectDir + '/current');

  local.log('Checking for stale releases');
  var releases = getReleases(local);

  if (releases.length > config.keepReleases) {
    var removeCount = releases.length - config.keepReleases;
    local.log('Removing ' + removeCount + ' stale release(s)');

    releases = releases.slice(0, removeCount);
    releases = releases.map(function (item) {
      return config.projectDir + '/releases/' + item;
      });

    local.exec('rm -rf ' + releases.join(' '));
  }
});

plan.local('deploy', function(local) {
  local.log('Create virtualenv');
  local.exec('cd ' + config.projectDir + '/current' + '; virtualenv env --no-site-packages -p ' + config.pythonPath);
});

plan.local('deploy', function(local) {
  local.log('Install the requirements');
  // use pip9 due to bug reported here: https://stackoverflow.com/questions/49854465/pythonpip-install-bson-error
  local.exec('cd ' + config.projectDir + '/current' + '; source env/bin/activate; pip install -U pip; pip install -r requirements.txt --no-cache-dir');
});

plan.local('deploy', function(local) {
  local.log('Copy over lightsheet-config.cfg');
  local.exec('cp ' + config.projectDir + '/lightsheet-config.cfg ' + config.projectDir + '/current/app/');
});

plan.local('deploy', function(local) {
  local.log('Copy over env_config.py');
  local.exec('cp ' + config.projectDir + '/env_config.py ' + config.projectDir + '/current/');
});

// plan.local('deploy', function(local) {
//   local.log('Create upload folder');
//   local.exec('cd ' + config.projectDir + '/current' + '; mkdir upload');
// });

plan.local('deploy', function(local) {
  local.log('Restart application');
  local.exec('sudo /usr/local/bin/flask_restart.sh');
});

plan.local('rollback', function(local) {
  local.log('Rolling back release');
  var releases = getReleases(local);
  if (releases.length > 1) {
    var oldCurrent = releases.pop();
    var newCurrent = releases.pop();
    local.log('Linking current to ' + newCurrent);
    local.exec('ln -nfs ' + config.projectDir + '/releases/' + newCurrent + ' '
      + config.projectDir + '/current');

    local.log('Removing ' + oldCurrent);
    local.sudo('rm -rf ' + config.projectDir + '/releases/' + oldCurrent, {user: config.root});
  }

});

plan.local(['default','uptime'], function(local) {
  local.exec('uptime');
  local.exec('whoami');
});

function getReleases(local) {
  var releases = local.exec('ls ' + config.projectDir +
    '/releases', {silent: true});

  if (releases.code === 0) {
    releases = releases.stdout.trim().split('\n');
    return releases;
  }

  return [];
}
