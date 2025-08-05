from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt     import Bcrypt
from flask_login      import LoginManager
from flask_migrate    import Migrate
from flask_wtf.csrf   import CSRFProtect

db         = SQLAlchemy()
bcrypt     = Bcrypt()
login_mgr  = LoginManager()
migrate   = Migrate()
csrf       = CSRFProtect()

