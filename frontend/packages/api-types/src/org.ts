/**
 * 产品契约生成类型：org
 *
 * 本文件由 `frontend/packages/api-types/scripts/generate.mjs` 生成，请勿手工修改。
 * 来源：deploy/contracts/org.json（产品契约快照，唯一事实源）。
 * 重新生成：pnpm run api-types:gen
 */
export interface paths {
    "/": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Root
         * @description 应用信息。
         *
         *     Returns:
         *         ApiResponse: {code, message, data:{name, version}}。
         */
        get: operations["root__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/org/data-source/dept-tree": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Dept Tree
         * @description 组织数据源 · 部门树（一次性返回、不分页；数据范围限定外的部门不入树）。
         */
        get: operations["get_dept_tree_api_v1_org_data_source_dept_tree_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/org/data-source/posts": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Posts
         * @description 组织数据源 · 岗位（关键字 / 部门含子级 / 状态 / 分页）。
         */
        get: operations["list_posts_api_v1_org_data_source_posts_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/org/data-source/users": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Users
         * @description 组织数据源 · 用户（关键字 / 部门 / 含子级 / 状态 / 分页）。
         *
         *     部门过滤口径：映射为「该部门含子树下岗位、且用户已分配该岗位」的候选集——
         *     用户归属部门归本域 `org_user_dept`（2026-10-09 起），**不经平台字段**（`sys_user` 不落组织字段）。
         */
        get: operations["list_users_api_v1_org_data_source_users_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/org/depts": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Depts
         * @description 部门树。
         *
         *     需要 org:query 权限；一次性返回（不分页），可按状态过滤。
         */
        get: operations["list_depts_api_v1_org_depts_get"];
        put?: never;
        /**
         * Create Dept
         * @description 新建部门。
         *
         *     需要 org:create 权限；部门编码必填且租户内唯一（格式受 `org.dept_code_pattern` 约束）；
         *     同父部门名称唯一；支持幂等键。
         */
        post: operations["create_dept_api_v1_org_depts_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/org/depts/{dept_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Dept
         * @description 部门详情（含 `ancestors` 路径）。
         *
         *     需要 org:query 权限；不存在抛 330051。
         */
        get: operations["get_dept_api_v1_org_depts__dept_id__get"];
        /**
         * Update Dept
         * @description 修改部门（编码 / 名称 / 排序 / 状态）。
         *
         *     需要 org:update 权限；编码可改（格式与唯一校验、自身同值豁免）；`version` 提供时做乐观锁比对（冲突转统一并发冲突）。
         */
        put: operations["update_dept_api_v1_org_depts__dept_id__put"];
        post?: never;
        /**
         * Delete Dept
         * @description 删除部门（有引用拒绝，软删除）。
         *
         *     需要 org:delete 权限；子部门 / 岗位 / 角色分配存在时拒绝（330054 / 330055 / 330056）。
         */
        delete: operations["delete_dept_api_v1_org_depts__dept_id__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/org/depts/{dept_id}/move": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        /**
         * Move Dept
         * @description 移动部门（级联维护子树 `ancestors`）。
         *
         *     需要 org:update 权限；防环（新父不得为自身或其后代，330053）。
         */
        put: operations["move_dept_api_v1_org_depts__dept_id__move_put"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/org/depts/{dept_id}/roles": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Dept Roles
         * @description 部门角色分配回显。
         *
         *     需要 org:query 权限。
         */
        get: operations["list_dept_roles_api_v1_org_depts__dept_id__roles_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/org/depts/{dept_id}/users": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Dept Users
         * @description 部门（含子树）归属用户列表。
         *
         *     需要 org:query 权限；用户名称回显经组织主数据只读契约（01_03）。
         */
        get: operations["list_dept_users_api_v1_org_depts__dept_id__users_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/org/posts": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Posts
         * @description 岗位列表（分页；按部门 / 状态 / 关键字筛选）。
         *
         *     需要 org:query 权限；排序字段经白名单校验。
         */
        get: operations["list_posts_api_v1_org_posts_get"];
        put?: never;
        /**
         * Create Post
         * @description 新建岗位。
         *
         *     需要 org:create 权限；岗位码租户内唯一且受格式约束；支持幂等键。
         */
        post: operations["create_post_api_v1_org_posts_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/org/posts/{post_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Post
         * @description 岗位详情。
         *
         *     需要 org:query 权限；不存在抛 330031。
         */
        get: operations["get_post_api_v1_org_posts__post_id__get"];
        /**
         * Update Post
         * @description 修改岗位（含岗位码）。
         *
         *     需要 org:update 权限；岗位码可改（格式与唯一校验、自身同值豁免）；`version` 提供时做乐观锁比对。
         */
        put: operations["update_post_api_v1_org_posts__post_id__put"];
        post?: never;
        /**
         * Delete Post
         * @description 删除岗位（有引用拒绝，软删除）。
         *
         *     需要 org:delete 权限；仍关联用户 / 角色分配时拒绝（330034 / 330035）。
         */
        delete: operations["delete_post_api_v1_org_posts__post_id__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/org/posts/{post_id}/roles": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Post Roles
         * @description 岗位角色分配回显。
         *
         *     需要 org:query 权限。
         */
        get: operations["list_post_roles_api_v1_org_posts__post_id__roles_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/org/posts/{post_id}/users": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Post Users
         * @description 岗位下用户列表。
         *
         *     需要 org:query 权限。
         */
        get: operations["list_post_users_api_v1_org_posts__post_id__users_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/org/resolve-names": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Resolve Names
         * @description 名称回显（`target` + `id_in` 逗号分隔；未命中项占位、不抛错）。
         */
        get: operations["resolve_names_api_v1_org_resolve_names_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/org/role-depts": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Role Depts
         * @description 按角色列已分配部门（「部门分配」插件）。
         *
         *     需要 org:query 权限。
         */
        get: operations["list_role_depts_api_v1_org_role_depts_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/org/role-depts/{role_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        /**
         * Assign Role Depts
         * @description 全量覆盖分配角色部门（diff 后增删单事务）。
         *
         *     需要 org:update 权限；`role_id` 对 bms 角色逻辑外键（不下库校验）；支持幂等键。
         */
        put: operations["assign_role_depts_api_v1_org_role_depts__role_id__put"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/org/role-depts/{role_id}/{dept_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        /**
         * Unassign Role Dept
         * @description 解绑单个角色-部门。
         *
         *     需要 org:update 权限；分配不存在抛 330091。
         */
        delete: operations["unassign_role_dept_api_v1_org_role_depts__role_id___dept_id__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/org/role-posts": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Role Posts
         * @description 按角色列已分配岗位（「岗位分配」插件）。
         *
         *     需要 org:query 权限。
         */
        get: operations["list_role_posts_api_v1_org_role_posts_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/org/role-posts/{role_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        /**
         * Assign Role Posts
         * @description 全量覆盖分配角色岗位（diff 后增删单事务）。
         *
         *     需要 org:update 权限；`role_id` 对 bms 角色逻辑外键（不下库校验）；支持幂等键。
         */
        put: operations["assign_role_posts_api_v1_org_role_posts__role_id__put"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/org/role-posts/{role_id}/{post_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        /**
         * Unassign Role Post
         * @description 解绑单个角色-岗位。
         *
         *     需要 org:update 权限；分配不存在抛 330081。
         */
        delete: operations["unassign_role_post_api_v1_org_role_posts__role_id___post_id__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/org/user-depts/{user_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List User Depts
         * @description 按用户查已分配部门（含主要部门）。
         *
         *     需要 org:query 权限；供 bms 用户管理页具名插槽插件回显。
         */
        get: operations["list_user_depts_api_v1_org_user_depts__user_id__get"];
        /**
         * Assign User Depts
         * @description 全量覆盖分配用户部门（diff 后增删单事务）。
         *
         *     需要 org:update 权限；单用户部门数受上限约束（330112）；被移除项若为主要部门则同事务清空标记；支持幂等键。
         */
        put: operations["assign_user_depts_api_v1_org_user_depts__user_id__put"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/org/user-depts/{user_id}/primary": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        /**
         * Set Primary Dept
         * @description 置位 / 清除主要部门（同事务互斥置位）。
         *
         *     需要 org:update 权限；`dept_id` 为空表示清除；置位目标须已分配，否则 330113；
         *     主要部门不参与角色解析（解析按全部已分配部门）。
         */
        put: operations["set_primary_dept_api_v1_org_user_depts__user_id__primary_put"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/org/user-depts/{user_id}/{dept_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        /**
         * Unassign User Dept
         * @description 解绑单个用户-部门。
         *
         *     需要 org:update 权限；关联不存在抛 330111；若被解绑项为主要部门则标记随之清空。
         */
        delete: operations["unassign_user_dept_api_v1_org_user_depts__user_id___dept_id__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/org/user-posts": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List User Posts
         * @description 按用户查已分配岗位。
         *
         *     需要 org:query 权限；供 bms 用户管理页具名插槽插件回显。
         */
        get: operations["list_user_posts_api_v1_org_user_posts_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/org/user-posts/{user_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        /**
         * Assign User Posts
         * @description 全量覆盖分配用户岗位（diff 后增删单事务）。
         *
         *     需要 org:update 权限；单用户岗位数受上限约束（330072）；支持幂等键。
         */
        put: operations["assign_user_posts_api_v1_org_user_posts__user_id__put"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/org/user-posts/{user_id}/primary": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        /**
         * Set Primary Post
         * @description 置位 / 清除主要岗位（同事务互斥置位）。
         *
         *     需要 org:update 权限；`post_id` 为空表示清除；置位目标须已分配，否则 330113；
         *     主要岗位不参与角色解析（解析按全部已分配岗位）。
         */
        put: operations["set_primary_post_api_v1_org_user_posts__user_id__primary_put"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/org/user-posts/{user_id}/{post_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        /**
         * Unassign User Post
         * @description 解绑单个用户-岗位。
         *
         *     需要 org:update 权限；关联不存在抛 330071。
         */
        delete: operations["unassign_user_post_api_v1_org_user_posts__user_id___post_id__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/org/user-roles": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get User Roles
         * @description 按用户解析其经岗位 / 部门获得的角色（并集去重；结果短时缓存 + 写侧失效代）。
         *
         *     供 bms 权限引擎跨服务汇总（用户直接角色 `sys_user_role` 由消费方合并）。
         */
        get: operations["get_user_roles_api_v1_org_user_roles_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/healthz": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Healthz
         * @description 存活检查端点。
         *
         *     Args:
         *         request: 当前请求（取服务身份）。
         *
         *     Returns:
         *         dict: 服务状态与身份，固定返回 {"status": "ok", "service": 名, "version": 版}。
         */
        get: operations["healthz_healthz_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/readyz": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Readyz
         * @description 就绪检查端点（启动完成态 + 停机摘流 + 注册表聚合）。
         *
         *     Args:
         *         request: 当前请求（取应用启动完成态 / 停机摘流标记 / 服务身份）。
         *         registry: 健康检查项注册表（依赖注入）。
         *
         *     Returns:
         *         JSONResponse: 全部就绪 200；未就绪、启动未完成或停机中 503。
         */
        get: operations["readyz_readyz_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
}
export type webhooks = Record<string, never>;
export interface components {
    schemas: {
        /**
         * ApiResponse
         * @description 统一响应体：`code=0` 成功，非 0 业务错误码。
         *
         *     - `data` 为业务数据（泛型）；失败时为 `null`；分页载荷复用分页契约基类。
         *     - 雪花 ID 在 JSON 中以字符串输出（`BaseSchema` 统一序列化口径）。
         */
        ApiResponse: {
            /**
             * Code
             * @default 0
             */
            code: number;
            /** Data */
            data?: unknown | null;
            /**
             * Message
             * @default ok
             */
            message: string;
        };
        /** ApiResponse[BasePageResponse[OrgPost]] */
        ApiResponse_BasePageResponse_OrgPost__: {
            /**
             * Code
             * @default 0
             */
            code: number;
            data?: components["schemas"]["BasePageResponse_OrgPost_"] | null;
            /**
             * Message
             * @default ok
             */
            message: string;
        };
        /** ApiResponse[BasePageResponse[OrgUser]] */
        ApiResponse_BasePageResponse_OrgUser__: {
            /**
             * Code
             * @default 0
             */
            code: number;
            data?: components["schemas"]["BasePageResponse_OrgUser_"] | null;
            /**
             * Message
             * @default ok
             */
            message: string;
        };
        /** ApiResponse[BasePageResponse[PostItem]] */
        ApiResponse_BasePageResponse_PostItem__: {
            /**
             * Code
             * @default 0
             */
            code: number;
            data?: components["schemas"]["BasePageResponse_PostItem_"] | null;
            /**
             * Message
             * @default ok
             */
            message: string;
        };
        /** ApiResponse[DeptItem] */
        ApiResponse_DeptItem_: {
            /**
             * Code
             * @default 0
             */
            code: number;
            data?: components["schemas"]["DeptItem"] | null;
            /**
             * Message
             * @default ok
             */
            message: string;
        };
        /** ApiResponse[DeptRoleIds] */
        ApiResponse_DeptRoleIds_: {
            /**
             * Code
             * @default 0
             */
            code: number;
            data?: components["schemas"]["DeptRoleIds"] | null;
            /**
             * Message
             * @default ok
             */
            message: string;
        };
        /** ApiResponse[DeptTree] */
        ApiResponse_DeptTree_: {
            /**
             * Code
             * @default 0
             */
            code: number;
            data?: components["schemas"]["DeptTree"] | null;
            /**
             * Message
             * @default ok
             */
            message: string;
        };
        /** ApiResponse[DeptUserIds] */
        ApiResponse_DeptUserIds_: {
            /**
             * Code
             * @default 0
             */
            code: number;
            data?: components["schemas"]["DeptUserIds"] | null;
            /**
             * Message
             * @default ok
             */
            message: string;
        };
        /** ApiResponse[OrgDeptTree] */
        ApiResponse_OrgDeptTree_: {
            /**
             * Code
             * @default 0
             */
            code: number;
            data?: components["schemas"]["OrgDeptTree"] | null;
            /**
             * Message
             * @default ok
             */
            message: string;
        };
        /** ApiResponse[OrgNameRefs] */
        ApiResponse_OrgNameRefs_: {
            /**
             * Code
             * @default 0
             */
            code: number;
            data?: components["schemas"]["OrgNameRefs"] | null;
            /**
             * Message
             * @default ok
             */
            message: string;
        };
        /** ApiResponse[OrgUserRoles] */
        ApiResponse_OrgUserRoles_: {
            /**
             * Code
             * @default 0
             */
            code: number;
            data?: components["schemas"]["OrgUserRoles"] | null;
            /**
             * Message
             * @default ok
             */
            message: string;
        };
        /** ApiResponse[PostItem] */
        ApiResponse_PostItem_: {
            /**
             * Code
             * @default 0
             */
            code: number;
            data?: components["schemas"]["PostItem"] | null;
            /**
             * Message
             * @default ok
             */
            message: string;
        };
        /** ApiResponse[PostRoleIds] */
        ApiResponse_PostRoleIds_: {
            /**
             * Code
             * @default 0
             */
            code: number;
            data?: components["schemas"]["PostRoleIds"] | null;
            /**
             * Message
             * @default ok
             */
            message: string;
        };
        /** ApiResponse[PostUserIds] */
        ApiResponse_PostUserIds_: {
            /**
             * Code
             * @default 0
             */
            code: number;
            data?: components["schemas"]["PostUserIds"] | null;
            /**
             * Message
             * @default ok
             */
            message: string;
        };
        /** ApiResponse[RoleDeptIds] */
        ApiResponse_RoleDeptIds_: {
            /**
             * Code
             * @default 0
             */
            code: number;
            data?: components["schemas"]["RoleDeptIds"] | null;
            /**
             * Message
             * @default ok
             */
            message: string;
        };
        /** ApiResponse[RolePostIds] */
        ApiResponse_RolePostIds_: {
            /**
             * Code
             * @default 0
             */
            code: number;
            data?: components["schemas"]["RolePostIds"] | null;
            /**
             * Message
             * @default ok
             */
            message: string;
        };
        /** ApiResponse[UserDeptIds] */
        ApiResponse_UserDeptIds_: {
            /**
             * Code
             * @default 0
             */
            code: number;
            data?: components["schemas"]["UserDeptIds"] | null;
            /**
             * Message
             * @default ok
             */
            message: string;
        };
        /** ApiResponse[UserPostIds] */
        ApiResponse_UserPostIds_: {
            /**
             * Code
             * @default 0
             */
            code: number;
            data?: components["schemas"]["UserPostIds"] | null;
            /**
             * Message
             * @default ok
             */
            message: string;
        };
        /** BasePageResponse[OrgPost] */
        BasePageResponse_OrgPost_: {
            /** List */
            list: components["schemas"]["OrgPost"][];
            /** Page */
            page: number;
            /** Size */
            size: number;
            /** Total */
            total: number;
        };
        /** BasePageResponse[OrgUser] */
        BasePageResponse_OrgUser_: {
            /** List */
            list: components["schemas"]["OrgUser"][];
            /** Page */
            page: number;
            /** Size */
            size: number;
            /** Total */
            total: number;
        };
        /** BasePageResponse[PostItem] */
        BasePageResponse_PostItem_: {
            /** List */
            list: components["schemas"]["PostItem"][];
            /** Page */
            page: number;
            /** Size */
            size: number;
            /** Total */
            total: number;
        };
        /**
         * DeptCreateRequest
         * @description 新建部门请求。
         */
        DeptCreateRequest: {
            /**
             * Code
             * @description 部门编码（租户内唯一；格式受 org.dept_code_pattern 约束）
             */
            code: string;
            /**
             * Name
             * @description 部门名称（同父唯一）
             */
            name: string;
            /**
             * Parent Id
             * @description 父部门 id（空 = 根部门）
             */
            parent_id?: number | null;
            /**
             * Sort
             * @description 同级排序
             * @default 0
             */
            sort: number;
        };
        /**
         * DeptItem
         * @description 部门明细（扁平）。
         */
        DeptItem: {
            /** Ancestors */
            ancestors: string;
            /** Code */
            code: string;
            /** Id */
            id: string;
            /** Name */
            name: string;
            /** Parent Id */
            parent_id?: string | null;
            /** Sort */
            sort: number;
            /** Status */
            status: string;
        };
        /**
         * DeptMoveRequest
         * @description 移动部门请求。
         */
        DeptMoveRequest: {
            /**
             * Parent Id
             * @description 新父部门 id（空 = 移至根层级）
             */
            parent_id?: number | null;
            /**
             * Version
             * @description 客户端版本（乐观锁比对）
             */
            version?: number | null;
        };
        /**
         * DeptRoleIds
         * @description 部门角色分配回显（角色 id 清单）。
         */
        DeptRoleIds: {
            /** Role Ids */
            role_ids?: number[];
        };
        /**
         * DeptTree
         * @description 部门树响应（一次性返回、不分页）。
         */
        DeptTree: {
            /** Items */
            items?: components["schemas"]["DeptTreeNode"][];
        };
        /**
         * DeptTreeNode
         * @description 部门树节点（递归；`children` 为子节点）。
         */
        DeptTreeNode: {
            /** Ancestors */
            ancestors: string;
            /** Children */
            children?: components["schemas"]["DeptTreeNode"][];
            /** Code */
            code: string;
            /** Id */
            id: string;
            /** Name */
            name: string;
            /** Parent Id */
            parent_id?: string | null;
            /** Sort */
            sort: number;
            /** Status */
            status: string;
        };
        /**
         * DeptUpdateRequest
         * @description 修改部门请求（未传字段不改）。
         */
        DeptUpdateRequest: {
            /**
             * Code
             * @description 部门编码（可改）
             */
            code?: string | null;
            /**
             * Name
             * @description 部门名称
             */
            name?: string | null;
            /**
             * Sort
             * @description 同级排序
             */
            sort?: number | null;
            /**
             * Status
             * @description 状态（enabled / disabled）
             */
            status?: string | null;
            /**
             * Version
             * @description 客户端版本（乐观锁比对）
             */
            version?: number | null;
        };
        /**
         * DeptUserIds
         * @description 部门（含子树）归属用户 id 清单。
         */
        DeptUserIds: {
            /** User Ids */
            user_ids?: number[];
        };
        /** HTTPValidationError */
        HTTPValidationError: {
            /** Detail */
            detail?: components["schemas"]["ValidationError"][];
        };
        /**
         * OrgDept
         * @description 组织部门（嵌套树节点；部门树一次性返回、不分页）。
         */
        OrgDept: {
            /**
             * Children
             * @description 子部门（嵌套树）
             */
            children?: components["schemas"]["OrgDept"][];
            /**
             * Code
             * @description 部门编码（租户内唯一）
             */
            code: string;
            /**
             * Id
             * @description 部门 ID
             */
            id: string;
            /**
             * Name
             * @description 部门名称
             */
            name: string;
            /**
             * Parent Id
             * @description 父部门 ID（None＝根）
             */
            parent_id?: string | null;
            /**
             * Sort
             * @description 排序值
             * @default 0
             */
            sort: number;
            /**
             * Status
             * @description 状态（enabled / disabled）
             * @default enabled
             */
            status: string;
        };
        /**
         * OrgDeptTree
         * @description 组织部门树响应（一次性返回、不分页；`items` 为根节点序列，子节点嵌套）。
         */
        OrgDeptTree: {
            /**
             * Items
             * @description 部门树根节点序列（`children` 嵌套）
             */
            items?: components["schemas"]["OrgDept"][];
        };
        /**
         * OrgNameRef
         * @description 批量回显项（按 id 回显名称；已删除 / 停用不抛错，以字段标记）。
         */
        OrgNameRef: {
            /**
             * Exists
             * @description 对象是否存在
             * @default true
             */
            exists: boolean;
            /**
             * Id
             * @description 对象 ID
             */
            id: string;
            /**
             * Name
             * @description 对象名称（不存在时为占位名）
             */
            name: string;
            /**
             * Status
             * @description 状态（enabled / disabled）
             * @default enabled
             */
            status: string;
            /**
             * Target
             * @description 目标类型（user / post / dept）
             * @default user
             */
            target: string;
        };
        /**
         * OrgNameRefs
         * @description 名称回显响应（按请求插入序返回；未命中项占位）。
         */
        OrgNameRefs: {
            /**
             * Items
             * @description 回显项序列（保持请求插入序）
             */
            items?: components["schemas"]["OrgNameRef"][];
        };
        /**
         * OrgPost
         * @description 组织岗位（展示所需最小字段）。
         */
        OrgPost: {
            /**
             * Code
             * @description 岗位编码
             */
            code: string;
            /**
             * Dept Id
             * @description 归属部门 ID
             */
            dept_id?: string | null;
            /**
             * Id
             * @description 岗位 ID
             */
            id: string;
            /**
             * Name
             * @description 岗位名称
             */
            name: string;
            /**
             * Sort
             * @description 排序值
             * @default 0
             */
            sort: number;
            /**
             * Status
             * @description 状态（enabled / disabled）
             * @default enabled
             */
            status: string;
        };
        /**
         * OrgUser
         * @description 组织用户（展示所需最小字段；手机号 / 邮箱默认脱敏）。
         */
        OrgUser: {
            /**
             * Avatar
             * @description 头像地址
             */
            avatar?: string | null;
            /**
             * Email
             * @description 邮箱（默认脱敏）
             */
            email?: string | null;
            /**
             * Id
             * @description 用户 ID
             */
            id: string;
            /**
             * Nickname
             * @description 昵称
             * @default
             */
            nickname: string;
            /**
             * Phone
             * @description 手机号（默认脱敏）
             */
            phone?: string | null;
            /**
             * Status
             * @description 状态（enabled / disabled）
             * @default enabled
             */
            status: string;
            /**
             * Username
             * @description 用户名
             */
            username: string;
        };
        /**
         * OrgUserRoles
         * @description 按用户解析其经岗位 / 部门获得的角色（并集去重；不含用户直接角色）。
         */
        OrgUserRoles: {
            /**
             * Role Ids
             * @description 角色 id 集合（岗位链在前、部门链补入，去重）
             */
            role_ids?: number[];
        };
        /**
         * PostCreateRequest
         * @description 新建岗位请求。
         */
        PostCreateRequest: {
            /**
             * Code
             * @description 岗位码（租户内唯一；格式受 org.post_code_pattern 约束）
             */
            code: string;
            /**
             * Dept Id
             * @description 归属部门 id（须存在且启用）
             */
            dept_id: number;
            /**
             * Name
             * @description 岗位名称
             */
            name: string;
            /**
             * Sort
             * @description 排序
             * @default 0
             */
            sort: number;
        };
        /**
         * PostItem
         * @description 岗位明细。
         */
        PostItem: {
            /** Code */
            code: string;
            /** Dept Id */
            dept_id: string;
            /** Id */
            id: string;
            /** Name */
            name: string;
            /** Sort */
            sort: number;
            /** Status */
            status: string;
        };
        /**
         * PostRoleIds
         * @description 岗位角色分配回显（角色 id 清单）。
         */
        PostRoleIds: {
            /** Role Ids */
            role_ids?: number[];
        };
        /**
         * PostUpdateRequest
         * @description 修改岗位请求（未传字段不改；`code` 可改）。
         */
        PostUpdateRequest: {
            /**
             * Code
             * @description 岗位码（可改）
             */
            code?: string | null;
            /**
             * Dept Id
             * @description 归属部门 id
             */
            dept_id?: number | null;
            /**
             * Name
             * @description 岗位名称
             */
            name?: string | null;
            /**
             * Sort
             * @description 排序
             */
            sort?: number | null;
            /**
             * Status
             * @description 状态（enabled / disabled）
             */
            status?: string | null;
            /**
             * Version
             * @description 客户端版本（乐观锁比对）
             */
            version?: number | null;
        };
        /**
         * PostUserIds
         * @description 岗位下用户 id 清单。
         */
        PostUserIds: {
            /** User Ids */
            user_ids?: number[];
        };
        /**
         * RoleDeptAssignRequest
         * @description 全量覆盖分配角色部门请求（diff 后增删）。
         */
        RoleDeptAssignRequest: {
            /**
             * Dept Ids
             * @description 目标部门 id 清单（全量覆盖）
             */
            dept_ids?: number[];
        };
        /**
         * RoleDeptIds
         * @description 角色已分配部门 id 清单。
         */
        RoleDeptIds: {
            /** Dept Ids */
            dept_ids?: number[];
        };
        /**
         * RolePostAssignRequest
         * @description 全量覆盖分配角色岗位请求（diff 后增删）。
         */
        RolePostAssignRequest: {
            /**
             * Post Ids
             * @description 目标岗位 id 清单（全量覆盖）
             */
            post_ids?: number[];
        };
        /**
         * RolePostIds
         * @description 角色已分配岗位 id 清单。
         */
        RolePostIds: {
            /** Post Ids */
            post_ids?: number[];
        };
        /**
         * UserDeptAssignRequest
         * @description 全量覆盖分配用户部门请求（diff 后增删）。
         */
        UserDeptAssignRequest: {
            /**
             * Dept Ids
             * @description 目标部门 id 清单（全量覆盖）
             */
            dept_ids?: number[];
        };
        /**
         * UserDeptIds
         * @description 用户已分配部门 id 清单与主要部门。
         */
        UserDeptIds: {
            /** Dept Ids */
            dept_ids?: number[];
            /**
             * Primary Dept Id
             * @description 主要部门 id（未设置时为空）
             */
            primary_dept_id?: string | null;
        };
        /**
         * UserDeptPrimaryRequest
         * @description 主要部门置位请求（不传 / `null` 表示清除主要标记）。
         */
        UserDeptPrimaryRequest: {
            /**
             * Dept Id
             * @description 主要部门 id；不传 / null 表示清除
             */
            dept_id?: number | null;
        };
        /**
         * UserPostAssignRequest
         * @description 全量覆盖分配用户岗位请求（diff 后增删）。
         */
        UserPostAssignRequest: {
            /**
             * Post Ids
             * @description 目标岗位 id 清单（全量覆盖）
             */
            post_ids?: number[];
        };
        /**
         * UserPostIds
         * @description 用户已分配岗位 id 清单与主要岗位。
         */
        UserPostIds: {
            /** Post Ids */
            post_ids?: number[];
            /**
             * Primary Post Id
             * @description 主要岗位 id（未设置时为空）
             */
            primary_post_id?: string | null;
        };
        /**
         * UserPostPrimaryRequest
         * @description 主要岗位置位请求（不传 / `null` 表示清除主要标记）。
         */
        UserPostPrimaryRequest: {
            /**
             * Post Id
             * @description 主要岗位 id；不传 / null 表示清除
             */
            post_id?: number | null;
        };
        /** ValidationError */
        ValidationError: {
            /** Context */
            ctx?: Record<string, never>;
            /** Input */
            input?: unknown;
            /** Location */
            loc: (string | number)[];
            /** Message */
            msg: string;
            /** Error Type */
            type: string;
        };
    };
    responses: never;
    parameters: never;
    requestBodies: never;
    headers: never;
    pathItems: never;
}
export type $defs = Record<string, never>;
export interface operations {
    root__get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
        };
    };
    get_dept_tree_api_v1_org_data_source_dept_tree_get: {
        parameters: {
            query?: {
                status?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse_OrgDeptTree_"];
                };
            };
            /** @description 未认证 */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description 无权限 */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description 资源不存在 */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
            /** @description 限流 */
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description 服务异常 */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
        };
    };
    list_posts_api_v1_org_data_source_posts_get: {
        parameters: {
            query?: {
                dept_id?: number | null;
                include_children?: boolean;
                status?: string | null;
                keyword?: string | null;
                /** @description 页码（从 1 起） */
                page?: number;
                /** @description 每页条数（默认 20，上限 200） */
                size?: number;
                /** @description 排序字段，逗号分隔多值（如 status,created_at） */
                order_by?: string | null;
                /** @description 排序方向数组，与 order_by 位置一一对应 */
                order?: string[] | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse_BasePageResponse_OrgPost__"];
                };
            };
            /** @description 未认证 */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description 无权限 */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description 资源不存在 */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
            /** @description 限流 */
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description 服务异常 */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
        };
    };
    list_users_api_v1_org_data_source_users_get: {
        parameters: {
            query?: {
                dept_id?: number | null;
                include_children?: boolean;
                status?: string | null;
                keyword?: string | null;
                /** @description 页码（从 1 起） */
                page?: number;
                /** @description 每页条数（默认 20，上限 200） */
                size?: number;
                /** @description 排序字段，逗号分隔多值（如 status,created_at） */
                order_by?: string | null;
                /** @description 排序方向数组，与 order_by 位置一一对应 */
                order?: string[] | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse_BasePageResponse_OrgUser__"];
                };
            };
            /** @description 未认证 */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description 无权限 */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description 资源不存在 */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
            /** @description 限流 */
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description 服务异常 */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
        };
    };
    list_depts_api_v1_org_depts_get: {
        parameters: {
            query?: {
                status?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse_DeptTree_"];
                };
            };
            /** @description 未认证 */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description 无权限 */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description 资源不存在 */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
            /** @description 限流 */
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description 服务异常 */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
        };
    };
    create_dept_api_v1_org_depts_post: {
        parameters: {
            query?: never;
            header?: {
                /** @description 幂等键（可选） */
                "Idempotency-Key"?: string | null;
            };
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["DeptCreateRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse_DeptItem_"];
                };
            };
            /** @description 未认证 */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description 无权限 */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description 资源不存在 */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
            /** @description 限流 */
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description 服务异常 */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
        };
    };
    get_dept_api_v1_org_depts__dept_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                dept_id: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse_DeptItem_"];
                };
            };
            /** @description 未认证 */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description 无权限 */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description 资源不存在 */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
            /** @description 限流 */
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description 服务异常 */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
        };
    };
    update_dept_api_v1_org_depts__dept_id__put: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                dept_id: number;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["DeptUpdateRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse_DeptItem_"];
                };
            };
            /** @description 未认证 */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description 无权限 */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description 资源不存在 */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
            /** @description 限流 */
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description 服务异常 */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
        };
    };
    delete_dept_api_v1_org_depts__dept_id__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                dept_id: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse_DeptItem_"];
                };
            };
            /** @description 未认证 */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description 无权限 */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description 资源不存在 */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
            /** @description 限流 */
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description 服务异常 */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
        };
    };
    move_dept_api_v1_org_depts__dept_id__move_put: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                dept_id: number;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["DeptMoveRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse_DeptItem_"];
                };
            };
            /** @description 未认证 */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description 无权限 */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description 资源不存在 */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
            /** @description 限流 */
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description 服务异常 */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
        };
    };
    list_dept_roles_api_v1_org_depts__dept_id__roles_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                dept_id: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse_DeptRoleIds_"];
                };
            };
            /** @description 未认证 */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description 无权限 */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description 资源不存在 */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
            /** @description 限流 */
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description 服务异常 */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
        };
    };
    list_dept_users_api_v1_org_depts__dept_id__users_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                dept_id: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse_DeptUserIds_"];
                };
            };
            /** @description 未认证 */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description 无权限 */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description 资源不存在 */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
            /** @description 限流 */
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description 服务异常 */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
        };
    };
    list_posts_api_v1_org_posts_get: {
        parameters: {
            query?: {
                dept_id?: number | null;
                status?: string | null;
                keyword?: string | null;
                /** @description 页码（从 1 起） */
                page?: number;
                /** @description 每页条数（默认 20，上限 200） */
                size?: number;
                /** @description 排序字段，逗号分隔多值（如 status,created_at） */
                order_by?: string | null;
                /** @description 排序方向数组，与 order_by 位置一一对应 */
                order?: string[] | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse_BasePageResponse_PostItem__"];
                };
            };
            /** @description 未认证 */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description 无权限 */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description 资源不存在 */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
            /** @description 限流 */
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description 服务异常 */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
        };
    };
    create_post_api_v1_org_posts_post: {
        parameters: {
            query?: never;
            header?: {
                /** @description 幂等键（可选） */
                "Idempotency-Key"?: string | null;
            };
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["PostCreateRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse_PostItem_"];
                };
            };
            /** @description 未认证 */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description 无权限 */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description 资源不存在 */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
            /** @description 限流 */
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description 服务异常 */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
        };
    };
    get_post_api_v1_org_posts__post_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                post_id: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse_PostItem_"];
                };
            };
            /** @description 未认证 */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description 无权限 */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description 资源不存在 */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
            /** @description 限流 */
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description 服务异常 */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
        };
    };
    update_post_api_v1_org_posts__post_id__put: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                post_id: number;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["PostUpdateRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse_PostItem_"];
                };
            };
            /** @description 未认证 */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description 无权限 */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description 资源不存在 */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
            /** @description 限流 */
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description 服务异常 */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
        };
    };
    delete_post_api_v1_org_posts__post_id__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                post_id: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse_PostItem_"];
                };
            };
            /** @description 未认证 */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description 无权限 */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description 资源不存在 */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
            /** @description 限流 */
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description 服务异常 */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
        };
    };
    list_post_roles_api_v1_org_posts__post_id__roles_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                post_id: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse_PostRoleIds_"];
                };
            };
            /** @description 未认证 */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description 无权限 */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description 资源不存在 */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
            /** @description 限流 */
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description 服务异常 */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
        };
    };
    list_post_users_api_v1_org_posts__post_id__users_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                post_id: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse_PostUserIds_"];
                };
            };
            /** @description 未认证 */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description 无权限 */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description 资源不存在 */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
            /** @description 限流 */
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description 服务异常 */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
        };
    };
    resolve_names_api_v1_org_resolve_names_get: {
        parameters: {
            query?: {
                target?: string;
                id_in?: string;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse_OrgNameRefs_"];
                };
            };
            /** @description 未认证 */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description 无权限 */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description 资源不存在 */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
            /** @description 限流 */
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description 服务异常 */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
        };
    };
    list_role_depts_api_v1_org_role_depts_get: {
        parameters: {
            query: {
                role_id: number;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse_RoleDeptIds_"];
                };
            };
            /** @description 未认证 */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description 无权限 */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description 资源不存在 */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
            /** @description 限流 */
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description 服务异常 */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
        };
    };
    assign_role_depts_api_v1_org_role_depts__role_id__put: {
        parameters: {
            query?: never;
            header?: {
                /** @description 幂等键（可选） */
                "Idempotency-Key"?: string | null;
            };
            path: {
                role_id: number;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["RoleDeptAssignRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse_RoleDeptIds_"];
                };
            };
            /** @description 未认证 */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description 无权限 */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description 资源不存在 */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
            /** @description 限流 */
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description 服务异常 */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
        };
    };
    unassign_role_dept_api_v1_org_role_depts__role_id___dept_id__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                role_id: number;
                dept_id: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse_RoleDeptIds_"];
                };
            };
            /** @description 未认证 */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description 无权限 */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description 资源不存在 */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
            /** @description 限流 */
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description 服务异常 */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
        };
    };
    list_role_posts_api_v1_org_role_posts_get: {
        parameters: {
            query: {
                role_id: number;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse_RolePostIds_"];
                };
            };
            /** @description 未认证 */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description 无权限 */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description 资源不存在 */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
            /** @description 限流 */
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description 服务异常 */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
        };
    };
    assign_role_posts_api_v1_org_role_posts__role_id__put: {
        parameters: {
            query?: never;
            header?: {
                /** @description 幂等键（可选） */
                "Idempotency-Key"?: string | null;
            };
            path: {
                role_id: number;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["RolePostAssignRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse_RolePostIds_"];
                };
            };
            /** @description 未认证 */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description 无权限 */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description 资源不存在 */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
            /** @description 限流 */
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description 服务异常 */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
        };
    };
    unassign_role_post_api_v1_org_role_posts__role_id___post_id__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                role_id: number;
                post_id: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse_RolePostIds_"];
                };
            };
            /** @description 未认证 */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description 无权限 */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description 资源不存在 */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
            /** @description 限流 */
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description 服务异常 */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
        };
    };
    list_user_depts_api_v1_org_user_depts__user_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                user_id: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse_UserDeptIds_"];
                };
            };
            /** @description 未认证 */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description 无权限 */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description 资源不存在 */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
            /** @description 限流 */
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description 服务异常 */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
        };
    };
    assign_user_depts_api_v1_org_user_depts__user_id__put: {
        parameters: {
            query?: never;
            header?: {
                /** @description 幂等键（可选） */
                "Idempotency-Key"?: string | null;
            };
            path: {
                user_id: number;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["UserDeptAssignRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse_UserDeptIds_"];
                };
            };
            /** @description 未认证 */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description 无权限 */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description 资源不存在 */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
            /** @description 限流 */
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description 服务异常 */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
        };
    };
    set_primary_dept_api_v1_org_user_depts__user_id__primary_put: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                user_id: number;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["UserDeptPrimaryRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse_UserDeptIds_"];
                };
            };
            /** @description 未认证 */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description 无权限 */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description 资源不存在 */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
            /** @description 限流 */
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description 服务异常 */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
        };
    };
    unassign_user_dept_api_v1_org_user_depts__user_id___dept_id__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                user_id: number;
                dept_id: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse_UserDeptIds_"];
                };
            };
            /** @description 未认证 */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description 无权限 */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description 资源不存在 */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
            /** @description 限流 */
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description 服务异常 */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
        };
    };
    list_user_posts_api_v1_org_user_posts_get: {
        parameters: {
            query: {
                user_id: number;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse_UserPostIds_"];
                };
            };
            /** @description 未认证 */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description 无权限 */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description 资源不存在 */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
            /** @description 限流 */
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description 服务异常 */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
        };
    };
    assign_user_posts_api_v1_org_user_posts__user_id__put: {
        parameters: {
            query?: never;
            header?: {
                /** @description 幂等键（可选） */
                "Idempotency-Key"?: string | null;
            };
            path: {
                user_id: number;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["UserPostAssignRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse_UserPostIds_"];
                };
            };
            /** @description 未认证 */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description 无权限 */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description 资源不存在 */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
            /** @description 限流 */
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description 服务异常 */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
        };
    };
    set_primary_post_api_v1_org_user_posts__user_id__primary_put: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                user_id: number;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["UserPostPrimaryRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse_UserPostIds_"];
                };
            };
            /** @description 未认证 */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description 无权限 */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description 资源不存在 */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
            /** @description 限流 */
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description 服务异常 */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
        };
    };
    unassign_user_post_api_v1_org_user_posts__user_id___post_id__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                user_id: number;
                post_id: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse_UserPostIds_"];
                };
            };
            /** @description 未认证 */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description 无权限 */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description 资源不存在 */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
            /** @description 限流 */
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description 服务异常 */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
        };
    };
    get_user_roles_api_v1_org_user_roles_get: {
        parameters: {
            query: {
                user_id: number;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse_OrgUserRoles_"];
                };
            };
            /** @description 未认证 */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description 无权限 */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description 资源不存在 */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
            /** @description 限流 */
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
            /** @description 服务异常 */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiResponse"];
                };
            };
        };
    };
    healthz_healthz_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
        };
    };
    readyz_readyz_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
        };
    };
}
