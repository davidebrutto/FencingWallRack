<?php
require __DIR__ . '/inc/bootstrap.php';
redirect_to(current_user() ? '/dashboard.php' : '/login.php');
