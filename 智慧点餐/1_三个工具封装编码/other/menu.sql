/*
 Navicat Premium Data Transfer

 Source Server         : 本地
 Source Server Type    : MySQL
 Source Server Version : 80042
 Source Host           : localhost:3306
 Source Schema         : menu

 Target Server Type    : MySQL
 Target Server Version : 80042
 File Encoding         : 65001

 Date: 25/11/2025 17:16:55
*/

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ----------------------------
-- Table structure for menu_items
-- ----------------------------
DROP TABLE IF EXISTS `menu_items`;
CREATE TABLE `menu_items`  (
  `id` int NOT NULL AUTO_INCREMENT COMMENT '菜品ID，主键自增',
  `dish_name` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '菜品名称',
  `price` decimal(8, 2) NOT NULL COMMENT '价格（元）',
  `description` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL COMMENT '菜品描述',
  `category` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '菜品分类',
  `spice_level` tinyint NULL DEFAULT 0 COMMENT '辣度等级：0-不辣，1-微辣，2-中辣，3-重辣',
  `flavor` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL COMMENT '口味特点',
  `main_ingredients` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL COMMENT '主要食材，多个食材用逗号分隔',
  `cooking_method` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL COMMENT '烹饪方法',
  `is_vegetarian` tinyint(1) NULL DEFAULT 0 COMMENT '是否素食：0-否，1-是',
  `allergens` varchar(200) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL COMMENT '过敏原信息，多个过敏原用逗号分隔',
  `is_available` tinyint(1) NULL DEFAULT 1 COMMENT '是否可供应：0-不可用，1-可用',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`) USING BTREE,
  INDEX `idx_category`(`category`) USING BTREE,
  INDEX `idx_is_available`(`is_available`) USING BTREE,
  INDEX `idx_is_vegetarian`(`is_vegetarian`) USING BTREE,
  INDEX `idx_price`(`price`) USING BTREE,
  INDEX `idx_spice_level`(`spice_level`) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 5 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci COMMENT = '菜单表' ROW_FORMAT = Dynamic;

-- ----------------------------
-- Records of menu_items
-- ----------------------------
INSERT INTO `menu_items` VALUES (1, '宫保鸡丁', 28.00, '经典川菜，鸡肉丁配花生米，酸甜微辣，口感丰富', '川菜', 2, '酸甜微辣', '鸡胸肉,花生米,青椒,红椒,葱段', '爆炒', 0, '花生,可能含有麸质', 1, '2025-07-01 10:45:02', '2025-07-01 10:45:02');
INSERT INTO `menu_items` VALUES (2, '麻婆豆腐', 18.00, '四川传统名菜，嫩滑豆腐配麻辣汤汁，下饭神器', '川菜', 3, '麻辣鲜香', '嫩豆腐,牛肉末,豆瓣酱,花椒', '烧炒', 0, '大豆,可能含有麸质', 1, '2025-07-01 10:45:02', '2025-09-26 14:43:58');
INSERT INTO `menu_items` VALUES (3, '清炒时蔬', 15.00, '新鲜时令蔬菜清炒，营养健康，口感清爽', '素食', 0, '清淡爽口', '时令蔬菜,蒜蓉', '清炒', 1, '', 1, '2025-07-01 10:45:02', '2025-09-26 14:53:33');
INSERT INTO `menu_items` VALUES (4, '红烧鲈鱼', 45.00, '新鲜鲈鱼红烧制作，肉质鲜美，营养丰富', '鲁菜', 1, '咸鲜微甜', '鲈鱼,生抽,老抽,冰糖,葱姜', '红烧', 0, '鱼类', 1, '2025-07-01 10:45:02', '2025-07-01 10:45:02');
INSERT INTO `menu_items` VALUES (5, '蒜蓉西兰花', 12.00, '新鲜西兰花配蒜蓉，营养丰富，适合减肥人群', '素食', 0, '蒜香清淡', '西兰花,大蒜,橄榄油', '蒸炒', 1, '无过敏源', 1, '2025-07-01 10:45:02', '2025-09-26 14:53:24');

-- ----------------------------
-- Table structure for order_items
-- ----------------------------
DROP TABLE IF EXISTS `order_items`;
CREATE TABLE `order_items`  (
  `id` int NOT NULL AUTO_INCREMENT,
  `order_id` int NOT NULL,
  `dish_id` int NOT NULL,
  `dish_name` varchar(200) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL,
  `quantity` int NOT NULL,
  `unit_price` decimal(10, 2) NOT NULL,
  `subtotal` decimal(10, 2) NOT NULL,
  PRIMARY KEY (`id`) USING BTREE,
  INDEX `dish_id`(`dish_id`) USING BTREE,
  INDEX `order_id`(`order_id`) USING BTREE,
  CONSTRAINT `order_items_ibfk_1` FOREIGN KEY (`order_id`) REFERENCES `orders` (`id`) ON DELETE CASCADE ON UPDATE RESTRICT,
  CONSTRAINT `order_items_ibfk_2` FOREIGN KEY (`dish_id`) REFERENCES `menu_items` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE = InnoDB AUTO_INCREMENT = 13 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_general_ci ROW_FORMAT = Dynamic;

-- ----------------------------
-- Records of order_items
-- ----------------------------
INSERT INTO `order_items` VALUES (1, 1, 2, '麻婆豆腐', 1, 18.00, 18.00);
INSERT INTO `order_items` VALUES (2, 2, 3, '清炒时蔬', 1, 15.00, 15.00);
INSERT INTO `order_items` VALUES (11, 6, 3, '清炒时蔬', 1, 15.00, 15.00);
INSERT INTO `order_items` VALUES (12, 7, 1, '宫保鸡丁', 1, 28.00, 28.00);
INSERT INTO `order_items` VALUES (13, 8, 1, '宫保鸡丁', 2, 28.00, 56.00);

-- ----------------------------
-- Table structure for orders
-- ----------------------------
DROP TABLE IF EXISTS `orders`;
CREATE TABLE `orders`  (
  `id` int NOT NULL AUTO_INCREMENT,
  `user_id` int NOT NULL,
  `order_no` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL,
  `contact_name` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL,
  `contact_phone` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL,
  `delivery_address` varchar(500) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL,
  `total_amount` decimal(10, 2) NOT NULL,
  `total_quantity` int NOT NULL,
  `status` tinyint NOT NULL DEFAULT 0,
  `delivery_distance` decimal(8, 2) NULL DEFAULT NULL,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`) USING BTREE,
  UNIQUE INDEX `order_no`(`order_no`) USING BTREE,
  INDEX `user_id`(`user_id`) USING BTREE,
  CONSTRAINT `orders_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE ON UPDATE RESTRICT
) ENGINE = InnoDB AUTO_INCREMENT = 8 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_general_ci ROW_FORMAT = Dynamic;

-- ----------------------------
-- Records of orders
-- ----------------------------
INSERT INTO `orders` VALUES (1, 2, '20250703105217285', '张三', '13812345678', '北京市海淀区中关村大街1号科技大厦A座1001室', 18.00, 1, 4, 15.10, '2025-07-03 10:52:17', '2025-07-03 11:05:43');
INSERT INTO `orders` VALUES (2, 2, '20250703110344662', '尚硅谷', '13624017478', '北京市昌平区回龙观东大街', 15.00, 1, 0, 3.19, '2025-07-03 11:03:44', '2025-07-03 11:03:44');
INSERT INTO `orders` VALUES (6, 2, '20250703162549259', '123', '13423456789', '北京市昌平区温都水城', 15.00, 1, 0, 1.62, '2025-07-03 16:25:49', '2025-07-03 16:25:49');
INSERT INTO `orders` VALUES (7, 2, '20251016212342363', 'hzk', '18438592661', '北京市昌平区回龙观', 28.00, 1, 0, 7.19, '2025-10-16 21:23:42', '2025-10-16 21:23:42');
INSERT INTO `orders` VALUES (8, 2, '20251016214926730', 'test', '13812345678', '北京市昌平区回龙观', 56.00, 2, 0, 7.19, '2025-10-16 21:49:26', '2025-10-16 21:49:26');

-- ----------------------------
-- Table structure for shopping_cart
-- ----------------------------
DROP TABLE IF EXISTS `shopping_cart`;
CREATE TABLE `shopping_cart`  (
  `id` int NOT NULL AUTO_INCREMENT,
  `user_id` int NOT NULL,
  `dish_id` int NOT NULL,
  `quantity` int NOT NULL DEFAULT 1,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`) USING BTREE,
  UNIQUE INDEX `unique_user_dish`(`user_id`, `dish_id`) USING BTREE,
  INDEX `dish_id`(`dish_id`) USING BTREE,
  CONSTRAINT `shopping_cart_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE ON UPDATE RESTRICT,
  CONSTRAINT `shopping_cart_ibfk_2` FOREIGN KEY (`dish_id`) REFERENCES `menu_items` (`id`) ON DELETE CASCADE ON UPDATE RESTRICT
) ENGINE = InnoDB AUTO_INCREMENT = 25 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci ROW_FORMAT = Dynamic;

-- ----------------------------
-- Records of shopping_cart
-- ----------------------------
INSERT INTO `shopping_cart` VALUES (19, 5, 1, 4, '2025-07-03 16:01:29', '2025-07-03 16:10:40');
INSERT INTO `shopping_cart` VALUES (20, 5, 2, 3, '2025-07-03 16:01:48', '2025-07-03 16:02:13');
INSERT INTO `shopping_cart` VALUES (21, 5, 3, 2, '2025-07-03 16:01:50', '2025-07-03 16:01:50');
INSERT INTO `shopping_cart` VALUES (22, 5, 4, 1, '2025-07-03 16:02:10', '2025-07-03 16:02:10');
INSERT INTO `shopping_cart` VALUES (23, 5, 5, 1, '2025-07-03 16:02:15', '2025-07-03 16:02:15');

-- ----------------------------
-- Table structure for users
-- ----------------------------
DROP TABLE IF EXISTS `users`;
CREATE TABLE `users`  (
  `id` int NOT NULL AUTO_INCREMENT,
  `username` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `password` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `email` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL,
  `phone` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `last_login` timestamp NULL DEFAULT NULL,
  `is_active` tinyint(1) NULL DEFAULT 1,
  PRIMARY KEY (`id`) USING BTREE,
  UNIQUE INDEX `username`(`username`) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 5 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci ROW_FORMAT = Dynamic;

-- ----------------------------
-- Records of users
-- ----------------------------
INSERT INTO `users` VALUES (1, 'admin', '8d969eef6ecad3c29a3a629280e686cf0c3f5d5a86aff3ca12020c923adc6c92', 'admin@example.com', NULL, '2025-07-02 09:46:39', NULL, 1);
INSERT INTO `users` VALUES (2, 'test', '8d969eef6ecad3c29a3a629280e686cf0c3f5d5a86aff3ca12020c923adc6c92', 'test@example.com', '13812345678', '2025-07-02 09:46:39', '2025-10-16 21:21:16', 1);
INSERT INTO `users` VALUES (3, 'testuser1', '85777f270ad7cf2a790981bbae3c4e484a1dc55e24a77390d692fbf1cffa12fa', 'testuser1@example.com', '13800138000', '2025-07-02 10:10:31', '2025-07-03 09:17:04', 1);
INSERT INTO `users` VALUES (4, 'test2', '8d969eef6ecad3c29a3a629280e686cf0c3f5d5a86aff3ca12020c923adc6c92', '123@qq.com', '13624007576', '2025-07-02 13:54:00', '2025-07-02 13:54:06', 1);
INSERT INTO `users` VALUES (5, 'testuser', '7e6e0c3079a08c5cc6036789b57e951f65f82383913ba1a49ae992544f1b4b6e', 'test@example.com', '13812345678', '2025-07-03 15:45:35', '2025-07-03 15:52:29', 1);

SET FOREIGN_KEY_CHECKS = 1;
