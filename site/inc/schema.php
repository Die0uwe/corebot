<?php
declare(strict_types=1);

/** Tabellen aanmaken (idempotent). Gebruikt door de installer en bij een nieuwe schemaversie. */
function install_schema(PDO $pdo): void
{
    $opt = 'ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci';
    $tables = [
        "create table if not exists settings (
            k varchar(64) not null primary key,
            v mediumtext null
        ) $opt",
        // Alleen een Discord-identiteit: geen e-mail, geen wachtwoord, geen tokens.
        "create table if not exists users (
            id char(24) not null primary key,
            discord_id varchar(24) not null,
            name varchar(80) not null,
            avatar varchar(64) null,
            created_at timestamp not null default current_timestamp,
            last_login timestamp null default null,
            unique key uq_users_discord (discord_id)
        ) $opt",
        // Servers van de gebruiker volgens Discord op het moment van inloggen of vernieuwen.
        "create table if not exists user_guilds (
            user_id char(24) not null,
            guild_id varchar(24) not null,
            name varchar(100) not null,
            icon varchar(64) null,
            is_owner tinyint(1) not null default 0,
            can_manage tinyint(1) not null default 0,
            updated_at timestamp not null default current_timestamp on update current_timestamp,
            primary key (user_id, guild_id),
            key idx_ug_guild (guild_id)
        ) $opt",
        // Servers waar de bot in zit (of zat). config = JSON {server, channels, channel_cfg, allow_member_tone}.
        "create table if not exists guilds (
            guild_id varchar(24) not null primary key,
            name varchar(100) not null default '',
            icon varchar(64) null,
            members int unsigned not null default 0,
            bot_present tinyint(1) not null default 0,
            bot_seen timestamp null default null,
            suspended tinyint(1) not null default 0,
            model varchar(80) not null default '',
            daily_cap int unsigned null,
            config mediumtext null,
            created_at timestamp not null default current_timestamp,
            updated_at timestamp not null default current_timestamp on update current_timestamp
        ) $opt",
        "create table if not exists guild_channels (
            guild_id varchar(24) not null,
            channel_id varchar(24) not null,
            name varchar(100) not null,
            type tinyint not null default 0,
            position int not null default 0,
            primary key (guild_id, channel_id)
        ) $opt",
        // Voorkeuren van een lid, gelden in alle servers waar CoreBot zit.
        "create table if not exists member_prefs (
            discord_id varchar(24) not null primary key,
            prefs mediumtext not null,
            updated_at timestamp not null default current_timestamp on update current_timestamp
        ) $opt",
        "create table if not exists usage_daily (
            day date not null,
            guild_id varchar(24) not null,
            answered int unsigned not null default 0,
            limited int unsigned not null default 0,
            errors int unsigned not null default 0,
            primary key (day, guild_id)
        ) $opt",
        // Leden die hun gegevens lieten wissen: de bot wist ook zijn geheugen en bevestigt dat.
        "create table if not exists forget_queue (
            discord_id varchar(24) not null primary key,
            created_at timestamp not null default current_timestamp
        ) $opt",
        "create table if not exists rate_events (
            id bigint unsigned not null auto_increment primary key,
            kind varchar(24) not null,
            subject varchar(64) not null,
            created_at timestamp not null default current_timestamp,
            key idx_rate (kind, subject, created_at)
        ) $opt",
        "create table if not exists audit_log (
            id bigint unsigned not null auto_increment primary key,
            user_id char(24) null,
            guild_id varchar(24) null,
            action varchar(40) not null,
            detail varchar(500) not null default '',
            created_at timestamp not null default current_timestamp,
            key idx_audit_guild (guild_id, created_at)
        ) $opt",
    ];
    foreach ($tables as $sql) $pdo->exec($sql);
}
